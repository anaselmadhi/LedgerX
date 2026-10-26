from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID

from sqlalchemy import func, select, text

from app.core.exceptions import DomainError
from app.db.models import Account, Transfer
from app.schemas.transfer import TransferCreate
from app.services.transfer_service import reverse_transfer, transfer_money
from tests.conftest import payload


def run_concurrently(sessions, request, keys):
    barrier = Barrier(2)

    def worker(key):
        with sessions() as session:
            try:
                with session.begin():
                    session.execute(text("SET LOCAL lock_timeout = '5s'"))
                    session.execute(text("SET LOCAL statement_timeout = '10s'"))
                    pid = session.scalar(text("SELECT pg_backend_pid()"))
                    barrier.wait(timeout=10)
                    transfer = transfer_money(session, request, key)
                    result = (201, transfer.id, pid)
                return result
            except DomainError as exc:
                return (exc.status_code, None, pid)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, key) for key in keys]
        return [future.result(timeout=20) for future in futures]


def test_concurrent_transfers_cannot_overspend(accounts, sessions):
    results = run_concurrently(sessions, TransferCreate(**payload(accounts, 8000)), ["a", "b"])
    assert sorted(result[0] for result in results) == [201, 409]
    assert len({result[2] for result in results}) == 2
    with sessions() as session:
        assert session.get(Account, UUID(accounts[0])).balance == 2000
        assert session.get(Account, UUID(accounts[1])).balance == 8000


def test_concurrent_same_key_executes_once(accounts, sessions):
    results = run_concurrently(
        sessions, TransferCreate(**payload(accounts, 8000)), ["same", "same"]
    )
    assert [result[0] for result in results] == [201, 201]
    assert results[0][1] == results[1][1]
    assert len({result[2] for result in results}) == 2
    with sessions() as session:
        assert session.get(Account, UUID(accounts[0])).balance == 2000
        assert session.scalar(select(func.count()).select_from(Transfer)) == 2  # includes funding


def test_reverse_direction_transfers_do_not_deadlock(client, accounts, sessions):
    client.post("/dev/funding", json={"destination_account_id": accounts[1], "amount": 10000})
    barrier = Barrier(2)

    def worker(pair):
        with sessions.begin() as session:
            pid = session.scalar(text("SELECT pg_backend_pid()"))
            barrier.wait(timeout=10)
            for _ in range(10):
                transfer_money(session, TransferCreate(**payload(pair, 100)))
            return pid

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, pair) for pair in (accounts, accounts[::-1])]
        assert len({f.result(timeout=20) for f in futures}) == 2
    with sessions() as session:
        assert session.get(Account, UUID(accounts[0])).balance == 10000
        assert session.get(Account, UUID(accounts[1])).balance == 10000


def test_concurrent_reversals_create_one_compensation(client, accounts, sessions):
    original = client.post("/transfers", json=payload(accounts)).json()["id"]
    barrier = Barrier(2)

    def worker(key):
        with sessions() as session:
            try:
                with session.begin():
                    barrier.wait(timeout=10)
                    result = reverse_transfer(session, UUID(original), "Refund", key)
                    result_id = result.id
                return (201, result_id)
            except DomainError as error:
                return (error.status_code, None)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, key) for key in ("refund-a", "refund-b")]
        assert sorted(f.result(timeout=20)[0] for f in futures) == [201, 409]
    with sessions() as session:
        assert session.get(Account, UUID(accounts[0])).balance == 10000
        assert session.get(Account, UUID(accounts[1])).balance == 0
        assert (
            session.scalar(
                select(func.count())
                .select_from(Transfer)
                .where(Transfer.reversal_of == UUID(original))
            )
            == 1
        )


def test_many_concurrent_debits_preserve_money(client, accounts, sessions):
    workers = 8
    barrier = Barrier(workers)

    def worker(index):
        with sessions() as session:
            try:
                with session.begin():
                    pid = session.scalar(text("SELECT pg_backend_pid()"))
                    barrier.wait(timeout=10)
                    transfer_money(
                        session, TransferCreate(**payload(accounts, 2000)), f"race-{index}"
                    )
                return (201, pid)
            except DomainError as error:
                return (error.status_code, pid)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(worker, range(workers)))
    assert len({pid for _, pid in results}) == workers
    assert sorted(status for status, _ in results) == [201] * 5 + [409] * 3
    assert client.get(f"/accounts/{accounts[0]}/balance").json()["balance"] == 0
    assert client.get(f"/accounts/{accounts[1]}/balance").json()["balance"] == 10000
    assert client.get("/operations/reconciliation").json()["consistent"] is True


def test_same_reversal_key_concurrently_returns_one_result(client, accounts, sessions):
    original = client.post("/transfers", json=payload(accounts)).json()["id"]
    barrier = Barrier(2)

    def worker():
        with sessions.begin() as session:
            barrier.wait(timeout=10)
            return reverse_transfer(session, UUID(original), "Refund", "one-refund").id

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker) for _ in range(2)]
        assert len({future.result(timeout=20) for future in futures}) == 1
    assert client.get(f"/accounts/{accounts[0]}/balance").json()["balance"] == 10000
