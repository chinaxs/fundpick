"""第三次独立验收：上一轮修复之外，核对真实成交语义与历史事件一致性。

已纳入默认回归；断言为正确产品行为，避免后续改动重新引入旧问题。
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from acceptance_rework import audit_book as audit_book
from acceptance_rework import book as book
from acceptance_rework import flow, overview, purchase
from acceptance_rework import target_fund as target_fund
from test_portfolio_flow import BASE, DAY, commit
from test_trade_fees import RULES, row

from app.services import sync_job
from app.services.trade_fee_math import redemption_fee


async def test_multi_platform_event_requires_explicit_platform(client, audit_book):
    await purchase(client, audit_book, platform="A", amount="100")
    await purchase(client, audit_book, platform="B", amount="200")
    response = await client.post(
        BASE + "/portfolio/flows",
        headers=audit_book["headers"],
        json={
            "code": audit_book["code"],
            "kind": "reinvest",
            "shares_delta": "10",
            "nav": "1",
            "effective_on": str(DAY + timedelta(days=1)),
        },
    )
    assert response.status_code == 422, "不能拿最大持仓平台冒充用户未提供的真实归属"


async def test_target_quantity_uses_target_net_amount(client, audit_book, target_fund):
    await purchase(client, audit_book)
    await flow(
        client,
        audit_book,
        "convert_out",
        shares_delta="-100",
        cash_amount="100",
        target_code=target_fund,
        target_nav="1",
        target_cash_amount="90",
    )
    holdings = (await overview(client, audit_book))["holdings"]
    target = next(item for item in holdings if item["code"] == target_fund)
    assert target["shares"] == 90, "转入金额90、净值1元，应得到90份，不能用转出金额100推算"


async def test_unknown_conversion_quantity_is_not_fabricated(client, audit_book, target_fund):
    await purchase(client, audit_book)
    response = await client.post(
        BASE + "/portfolio/flows",
        headers=audit_book["headers"],
        json={
            "code": audit_book["code"],
            "kind": "convert_out",
            "shares_delta": "-50",
            "target_code": target_fund,
            "effective_on": str(DAY + timedelta(days=1)),
        },
    )
    assert response.status_code == 422, "未知转入份额和净值不能直接复制转出份额成为持仓"


async def test_incoming_conversion_respects_incoming_shares(client, audit_book, target_fund):
    await purchase(client, audit_book, amount="100", nav="2")  # 源基金50份
    response = await client.post(
        BASE + "/portfolio/flows",
        headers=audit_book["headers"],
        json={
            "code": target_fund,
            "kind": "convert_in",
            "shares_delta": "100",
            "nav": "1",
            "cash_amount": "100",
            "target_code": audit_book["code"],
            "target_nav": "2",
            "target_shares": "50",
            "effective_on": str(DAY + timedelta(days=1)),
        },
    )
    assert response.status_code == 201, "转入100份不能用来校验源基金是否持有100份（实际只转出50份）"


async def test_backdated_conversion_cannot_invalidate_existing_sale(
    client, audit_book, target_fund
):
    await purchase(client, audit_book)
    await commit(
        client,
        audit_book,
        {
            "code": audit_book["code"],
            "kind": "sell",
            "shares": "80",
            "nav_mode": "manual",
            "nav": "1",
            "fee": "0",
            "confirmed_on": str(DAY + timedelta(days=3)),
        },
    )
    response = await client.post(
        BASE + "/portfolio/flows",
        headers=audit_book["headers"],
        json={
            "code": audit_book["code"],
            "kind": "convert_out",
            "shares_delta": "-80",
            "target_shares": "80",
            "target_nav": "1",
            "target_code": target_fund,
            "effective_on": str(DAY + timedelta(days=1)),
        },
    )
    assert response.status_code in (409, 422), "补录转换不能让已有后续卖出变为-60份"


async def test_request_key_cannot_silently_discard_changed_amount(client, audit_book):
    await purchase(client, audit_book)
    payload = {
        "code": audit_book["code"],
        "kind": "dividend",
        "cash_amount": "10",
        "effective_on": str(DAY + timedelta(days=1)),
        "request_key": str(uuid4()),
    }
    first = await client.post(
        BASE + "/portfolio/flows", headers=audit_book["headers"], json=payload
    )
    assert first.status_code == 201
    changed = await client.post(
        BASE + "/portfolio/flows",
        headers=audit_book["headers"],
        json={**payload, "cash_amount": "20"},
    )
    assert changed.status_code == 409, "相同键不同金额必须冲突，不能成功响应旧10元并丢弃新20元"


async def test_deleted_flow_is_not_resurrected_by_network_retry(client, audit_book):
    await purchase(client, audit_book)
    payload = {
        "code": audit_book["code"],
        "kind": "dividend",
        "cash_amount": "10",
        "effective_on": str(DAY + timedelta(days=1)),
        "request_key": str(uuid4()),
    }
    created = await client.post(
        BASE + "/portfolio/flows", headers=audit_book["headers"], json=payload
    )
    assert created.status_code == 201
    deleted = await client.delete(
        BASE + f"/portfolio/flows/{created.json()['data']['id']}", headers=audit_book["headers"]
    )
    assert deleted.status_code == 200
    retried = await client.post(
        BASE + "/portfolio/flows", headers=audit_book["headers"], json=payload
    )
    assert retried.status_code == 409, "删除后不能因旧请求重试把分红重新入账"


def test_historical_sale_fee_ignores_later_company_actions():
    rows = [
        row(1, "buy", "100", date(2026, 1, 1)),
        row(2, "buy", "100", date(2026, 1, 10)),
    ]
    later_conversion = SimpleNamespace(
        id=3,
        kind="convert_out",
        effective_on=date(2026, 1, 20),
        shares_delta=Decimal(-100),
        cash_amount=Decimal(100),
        nav=Decimal(1),
        platform="A",
    )
    result = redemption_fee(
        RULES, rows, Decimal(100), date(2026, 1, 11), Decimal(1), "A", [later_conversion]
    )
    assert result is not None
    assert result[0] == Decimal("0.50"), (
        "1月11日卖出应使用当日FIFO，不能先扣掉1月20日转换转出的老批次"
    )


@pytest.mark.parametrize(
    "command",
    [
        "python -m scripts.sync_funds --job-id 420 --mode quick",
        "/usr/local/bin/redis-server *:6379",
    ],
)
def test_pid_ownership_requires_exact_job_and_command(monkeypatch, command):
    started = datetime.now() - timedelta(days=1)

    def field(pid, name):
        return command if name == "command" else started.strftime("%a %b %d %H:%M:%S %Y")

    monkeypatch.setattr(sync_job, "_ps_field", field)
    job = SimpleNamespace(id=42, started_at=datetime.now() - timedelta(hours=1))
    assert sync_job._pid_belongs(12345, job) is False, (
        "不能凭job-id前缀或更早的启动时间确认进程归属"
    )
