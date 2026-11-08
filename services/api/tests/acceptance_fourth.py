"""独立验收回归：转换资金守恒、所有写入的历史有效性。"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from acceptance_rework import audit_book as audit_book
from acceptance_rework import book as book
from acceptance_rework import flow, overview, purchase
from acceptance_rework import target_fund as target_fund
from test_portfolio_flow import BASE, DAY

from app.services import sync_job
from scripts import restore_drill


async def test_conversion_fee_difference_is_in_total_profit(client, audit_book, target_fund):
    await purchase(client, audit_book)  # 外部投入100元。
    await flow(
        client,
        audit_book,
        "convert_out",
        shares_delta="-100",
        cash_amount="100",
        target_code=target_fund,
        target_shares="90",
        target_nav="1",
        target_cash_amount="90",
    )
    data = await overview(client, audit_book)
    summary = data["summary"]
    # 源基金清仓、目标市值90元，10元费用差不能随转换消失。
    expected = (
        summary["total_market_value"] + summary["total_sell_amount"] - summary["total_buy_amount"]
    )
    assert summary["total_return"] == expected == -10


async def test_historical_sell_cannot_break_later_conversion(client, audit_book, target_fund):
    await purchase(client, audit_book)
    await flow(
        client,
        audit_book,
        "convert_out",
        shares_delta="-80",
        cash_amount="80",
        target_code=target_fund,
        target_shares="80",
        target_nav="1",
        effective_on=str(DAY + timedelta(days=3)),
    )
    request = {
        "code": audit_book["code"],
        "kind": "sell",
        "shares": "80",
        "fee": "0",
        "nav_mode": "manual",
        "nav": "1",
        "confirmed_on": str(DAY + timedelta(days=1)),
    }
    preview = await client.post(
        BASE + "/transactions/preview", json=request, headers=audit_book["headers"]
    )
    if preview.status_code in (409, 422):
        return
    assert preview.status_code == 200, preview.text
    response = await client.post(
        BASE + "/transactions",
        headers=audit_book["headers"],
        json={
            "request": request,
            "preview_hash": preview.json()["data"]["preview_hash"],
            "request_key": str(uuid4()),
        },
    )
    assert response.status_code in (409, 422), (
        "公司行为新增已验证整本账，但买卖写入也要验证：100份同时支持历史卖出80和后续转换80会变-60份"
    )


def test_script_name_must_be_executable_module_not_argument_text(monkeypatch):
    command = "python /opt/report.py --label scripts.sync_funds --job-id 42"
    started = datetime.now() - timedelta(minutes=1)

    def field(pid, name):
        return command if name == "command" else started.strftime("%a %b %d %H:%M:%S %Y")

    monkeypatch.setattr(sync_job, "_ps_field", field)
    job = SimpleNamespace(id=42, started_at=started)
    assert sync_job._pid_belongs(123, job) is False, "普通参数里含脚本名称不能据此认领该PID"


async def test_restore_integrity_checks_do_not_skip_existing_empty_users(monkeypatch):
    class Connection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def execute(self, sql):
            text = str(sql)
            value = 1 if "auth_sessions" in text else 0
            return SimpleNamespace(
                scalar_one=lambda: value, scalar_one_or_none=lambda: "i9c4e1f82a37"
            )

    class Engine:
        def connect(self):
            return Connection()

        async def dispose(self):
            pass

    monkeypatch.setattr(restore_drill, "create_async_engine", lambda *args, **kwargs: Engine())
    counts = dict.fromkeys(restore_drill.CHECK_TABLES, 0)
    counts["funds"] = 1
    counts["auth_sessions"] = 1
    results, _ = await restore_drill._integrity_checks("isolated_test", counts)
    sessions = next(result for result in results if result["name"] == "会员会话的主体存在")
    assert sessions["ok"] is False, "users存在但为空时必须发现孤儿会话，不能把0行误认为缺表并跳过"
