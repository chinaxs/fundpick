"""第二轮独立验收：校验真实资金、平台份额与返工生命周期边界。

这些测试断言产品应满足的行为；失败即为返工缺口，不把当前错误写成预期。
"""

import asyncio
import io
import subprocess
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from test_acceptance_review import audit_book as audit_book
from test_portfolio_flow import BASE, DAY, buy, commit
from test_portfolio_flow import book as book

from app.db.session import async_session_factory
from app.main import app
from app.models.fund import Fund
from app.models.member_activity import MemberActivity
from app.models.portfolio_flow import FundPortfolioFlow
from app.models.user import User
from app.repositories.engagement import EngagementRepository
from app.services import sync_job
from scripts import backup_db, restore_drill


@pytest.fixture
async def target_fund(audit_book):
    async with async_session_factory() as session:
        code = f"{700000 + uuid4().int % 100000:06d}"
        while await session.scalar(select(Fund.id).where(Fund.code == code)):
            code = f"{700000 + uuid4().int % 100000:06d}"
        fund = Fund(
            code=code,
            name="第二轮验收目标基金",
            type="bond",
            latest_nav=1,
            latest_nav_date=date.today(),
        )
        session.add(fund)
        await session.commit()
        fund_id = fund.id
    yield code
    async with async_session_factory() as session:
        await session.execute(
            delete(FundPortfolioFlow).where(
                (FundPortfolioFlow.fund_id == fund_id)
                | (FundPortfolioFlow.target_fund_id == fund_id)
            )
        )
        await session.execute(delete(Fund).where(Fund.id == fund_id))
        await session.commit()


async def purchase(client, account, *, platform=None, amount="100", nav="1"):
    return await commit(
        client,
        account,
        buy(
            account,
            amount=amount,
            nav=nav,
            fee="0",
            **({"record_source": "estimated", "platform": platform} if platform else {}),
        ),
    )


async def flow(client, account, kind, **values):
    response = await client.post(
        BASE + "/portfolio/flows",
        headers=account["headers"],
        json={
            "code": account["code"],
            "kind": kind,
            "effective_on": str(DAY + timedelta(days=1)),
            **values,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def overview(client, account):
    response = await client.get(BASE + "/portfolio", headers=account["headers"])
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_reinvest_preserves_total_return(client, audit_book):
    await purchase(client, audit_book)
    await flow(client, audit_book, "reinvest", shares_delta="10", nav="1", cash_amount="10")
    data = await overview(client, audit_book)
    # 100 元外部本金 + 10 元红利再投 → 110 份。再投并无额外外部支出。
    expected = (
        data["summary"]["total_market_value"]
        + data["summary"]["total_sell_amount"]
        - data["summary"]["total_buy_amount"]
    )
    assert data["summary"]["total_return"] == expected


async def test_reinvestment_cannot_be_sold_twice_across_platforms(client, audit_book):
    await purchase(client, audit_book, platform="A")
    await purchase(client, audit_book, platform="B")
    # 契约调整（2026-11-09）：多平台必须指定归属，不能再让服务端猜；
    # 但"同一笔再投不能让两个平台各卖一遍"的断言保持不变。
    await flow(
        client, audit_book, "reinvest", shares_delta="10", nav="1", cash_amount="10", platform="A"
    )
    accepted = []
    for platform in ("A", "B"):
        response = await client.post(
            BASE + "/transactions/preview",
            headers=audit_book["headers"],
            json={
                "code": audit_book["code"],
                "kind": "sell",
                "record_source": "estimated",
                "platform": platform,
                "confirmed_on": str(DAY + timedelta(days=2)),
                "nav_mode": "manual",
                "nav": "1",
                "shares": "110",
                "fee": "0",
            },
        )
        accepted.append(response.status_code)
    assert accepted != [200, 200], f"总计 210 份却允许 A/B 平台各卖 110 份：{accepted}"


async def test_transfer_retains_actual_target_quantity(client, audit_book, target_fund):
    await purchase(client, audit_book, amount="200", nav="2")
    await flow(
        client,
        audit_book,
        "convert_out",
        shares_delta="-50",
        nav="2",
        cash_amount="100",
        target_code=target_fund,
        target_shares="100",
    )
    data = await overview(client, audit_book)
    target = next(item for item in data["holdings"] if item["code"] == target_fund)
    assert target["shares"] == 100, "50 份×2元转为100份×1元，不应复制为50份"


async def test_transfer_only_position_is_marked_held(client, audit_book, target_fund):
    await purchase(client, audit_book)
    # 契约调整：转入份额不能由服务端复制，必须给出目标侧成交数据
    await flow(
        client,
        audit_book,
        "convert_out",
        shares_delta="-50",
        target_code=target_fund,
        target_shares="50",
        target_nav="1",
    )
    response = await client.get(BASE + "/holding-codes", headers=audit_book["headers"])
    assert response.status_code == 200, response.text
    assert target_fund in response.json()["data"]


async def test_deleting_split_cannot_make_later_sale_negative(client, audit_book):
    await purchase(client, audit_book)
    split = await flow(client, audit_book, "split", ratio="2")
    await commit(
        client,
        audit_book,
        {
            "code": audit_book["code"],
            "kind": "sell",
            "shares": "150",
            "fee": "0",
            "confirmed_on": str(DAY + timedelta(days=2)),
            "nav_mode": "manual",
            "nav": "1",
        },
    )
    deleted = await client.delete(
        BASE + f"/portfolio/flows/{split['id']}", headers=audit_book["headers"]
    )
    assert deleted.status_code in (409, 422), "不能删除支持后续卖出的拆分，留下 -50 份余额"


async def test_concurrent_transfers_cannot_oversell(client, audit_book, target_fund, monkeypatch):
    from app.services.portfolio_tools import PortfolioToolsService

    await purchase(client, audit_book)
    original = PortfolioToolsService._consumed_cost

    async def synchronized_cost(self, *args):
        result = await original(self, *args)
        # 放大读余额到落库之间的并发窗口；加锁后第二次读取会等第一次提交。
        await asyncio.sleep(0.1)
        return result

    monkeypatch.setattr(PortfolioToolsService, "_consumed_cost", synchronized_cost)
    payload = {
        "code": audit_book["code"],
        "kind": "convert_out",
        "shares_delta": "-80",
        "target_code": target_fund,
        # 契约调整：补上目标侧成交数据，否则会在余额校验前就被拒绝，
        # 测不到"并发送出只能成功一次"这一点
        "target_shares": "80",
        "target_nav": "1",
        "effective_on": str(DAY + timedelta(days=1)),
    }
    responses = await asyncio.gather(
        *[
            client.post(BASE + "/portfolio/flows", headers=audit_book["headers"], json=payload)
            for _ in range(2)
        ]
    )
    assert sum(response.status_code == 201 for response in responses) <= 1


async def test_missing_latest_nav_keeps_portfolio_readable(client, audit_book):
    await purchase(client, audit_book)
    async with async_session_factory() as session:
        fund = await session.get(Fund, audit_book["fund_id"])
        fund.latest_nav = None
        await session.commit()
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as transport:
        response = await transport.get(BASE + "/portfolio", headers=audit_book["headers"])
    assert response.status_code == 200, "缺净值时应显示无法估值，不能返回500"


async def test_nav_before_split_cannot_value_post_split_shares(client, audit_book):
    await purchase(client, audit_book)
    await flow(client, audit_book, "split", ratio="2")
    async with async_session_factory() as session:
        fund = await session.get(Fund, audit_book["fund_id"])
        fund.latest_nav = Decimal("1")
        fund.latest_nav_date = DAY  # 净值仍在拆分前，不能乘拆分后200份。
        await session.commit()
    data = await overview(client, audit_book)
    assert data["holdings"][0]["market_value"] is None


async def test_email_domain_excludes_test_member(audit_book):
    async with async_session_factory() as session:
        before = await EngagementRepository(session).total_users()
    async with async_session_factory() as session:
        user = await session.get(User, audit_book["user_id"])
        user.email = f"{uuid4().hex}@example.com"
        await session.commit()
    async with async_session_factory() as session:
        after = await EngagementRepository(session).total_users()
    assert after == before - 1, "example.com 邮箱应从真实会员统计排除"


async def test_active_seven_days_does_not_include_eighth_day(audit_book):
    async with async_session_factory() as session:
        await session.execute(
            delete(MemberActivity).where(MemberActivity.user_id == audit_book["user_id"])
        )
        await session.commit()
        before = await EngagementRepository(session).active_users(7)
    async with async_session_factory() as session:
        session.add(
            MemberActivity(
                user_id=audit_book["user_id"],
                activity_date=date.today() - timedelta(days=7),
                last_seen_at=datetime.now() - timedelta(days=7),
            )
        )
        await session.commit()
    async with async_session_factory() as session:
        after = await EngagementRepository(session).active_users(7)
    assert after == before, "含今天的近7日不应再计入7天前（第8个日期）"


def test_backup_checksum_matches_written_backup(tmp_path, monkeypatch):
    class DumpProcess:
        stdout = io.BytesIO(b"CREATE TABLE funds (id INT); INSERT INTO funds VALUES (1);\n")

        def wait(self):
            return 0

    monkeypatch.setattr(backup_db, "BACKUP_DIR", tmp_path)
    monkeypatch.setattr(backup_db.shutil, "which", lambda _: "/fake/mysqldump")
    monkeypatch.setattr(backup_db.subprocess, "Popen", lambda *args, **kwargs: DumpProcess())
    result = backup_db.run_backup()
    assert result["ok"] is True
    assert restore_drill._checksum_matches(tmp_path / result["file"]) is True


async def test_restore_refuses_mismatched_checksum(tmp_path, monkeypatch):
    backup = tmp_path / "tampered.sql.gz"
    backup.write_bytes(b"tampered")
    executed = []

    async def fake_execute(database, sql):
        executed.append(sql)

    async def fake_counts(database):
        return dict.fromkeys(restore_drill.CHECK_TABLES, 1)

    monkeypatch.setattr(restore_drill, "BACKUP_DIR", tmp_path)
    monkeypatch.setattr(restore_drill, "_checksum_matches", lambda _: False)
    monkeypatch.setattr(restore_drill, "_execute", fake_execute)
    monkeypatch.setattr(restore_drill, "_import_dump", lambda *args: None)
    monkeypatch.setattr(restore_drill, "_table_counts", fake_counts)
    result = await restore_drill.drill(backup)
    assert result["ok"] is False and not executed, "摘要不符必须在导入前失败，不能报告恢复成功"


async def test_recovery_does_not_release_job_until_process_exits(monkeypatch):
    proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); "
            "print('ready',flush=True); time.sleep(30)",
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert proc.stdout.readline().strip() == "ready"
        job = SimpleNamespace(
            id=999999,
            status="running",
            pid=proc.pid,
            timeout_seconds=1,
            started_at=datetime.now() - timedelta(seconds=5),
            cancel_requested=False,
            log_file=None,
        )
        service = sync_job.SyncJobService(AsyncMock())
        monkeypatch.setattr(sync_job, "_read_result", lambda _: None)
        monkeypatch.setattr(service, "_apply_progress", AsyncMock())
        await service._reconcile(job)
        assert proc.poll() is not None or job.status in sync_job.ACTIVE_STATUSES, (
            "子进程仍存活时不能释放互斥并声称已终止，必须等待退出或升级SIGKILL"
        )
    finally:
        proc.kill()
        proc.wait(timeout=5)


def test_real_intraday_parser_preserves_shanghai_timezone(monkeypatch):
    from app.datasources import eastmoney

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, *args, **kwargs):
            return SimpleNamespace(
                raise_for_status=lambda: None,
                json=lambda: {
                    "data": {
                        "name": "上证指数",
                        "preClose": 3000,
                        "trends": ["2026-11-06 15:00,3000,3010,3015,2995,100,301000,3005"],
                    }
                },
            )

    monkeypatch.setattr(eastmoney.httpx, "Client", Client)
    result = eastmoney.fetch_intraday("1.000001")
    assert result is not None
    assert result.points[-1].moment.utcoffset() == timedelta(hours=8), (
        "真实上游时间缺少+08:00会被异地浏览器误读；现有测试桩已预先带时区，漏检此问题"
    )
