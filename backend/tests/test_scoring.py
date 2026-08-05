"""评分纯函数测试（R-401/R-402/R-403）——全局唯一口径。"""

from app.scoring import calc_hot_score, hot_level, importance_rank, normalize_hot_score


def test_hot_score_formula():
    # likes×10 + rt×5 + log10(views)×2
    expected = 10 * 10 + 4 * 5 + 3 * 2
    assert calc_hot_score(like_count=10, retweet_count=4, view_count=1000) == expected


def test_hot_score_none_and_zero_views():
    assert calc_hot_score(None, None, None) == 0.0  # log10(1)*2 = 0
    assert calc_hot_score(0, 0, 0) == 0.0


def test_importance_rank_order():
    assert importance_rank("urgent") < importance_rank("high")
    assert importance_rank("high") < importance_rank("medium")
    assert importance_rank("medium") < importance_rank("low")
    assert importance_rank("unknown") == importance_rank("low")


def test_normalize_bounds():
    assert normalize_hot_score(0) == 0
    assert normalize_hot_score(-5) == 0
    assert normalize_hot_score(1e12) == 100  # 封顶


def test_hot_level_labels():
    assert hot_level(0) == "温"
    assert hot_level(1e6) == "爆"
