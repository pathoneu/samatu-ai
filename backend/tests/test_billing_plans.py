from billing.plans import PLAN_BY_ID, PUBLIC_PLANS, QUOTA_POLICY

def test_approved_tiers_exact():
    pro = PLAN_BY_ID["pro"]
    studio = PLAN_BY_ID["studio"]
    assert pro["price_eur"] == 49 and pro["monthly_quota"] == 10 and pro["overage_eur"] == 8
    assert studio["price_eur"] == 149 and studio["monthly_quota"] == 35 and studio["overage_eur"] == 5
    assert PLAN_BY_ID["free"]["monthly_quota"] == 1
    assert PLAN_BY_ID["oneoff"]["price_eur"] == 12

def test_default_quota_policy_is_expire():
    assert QUOTA_POLICY == "expire"

def test_f2f3_gated_to_paid():
    assert "f2f3_export" in PLAN_BY_ID["pro"]["features"]
    assert "f2f3_export" not in PLAN_BY_ID["free"]["features"]
