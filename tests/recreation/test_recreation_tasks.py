import csv
from pathlib import Path
import json

from navi_bench.base import DatasetItem, instantiate
from navi_bench.recreation.demo_recreation import load_scenarios
from navi_bench.recreation.recreation_url_match import RecreationUrlMatch


ROOT = Path(__file__).resolve().parents[2]
TASKS_CSV = ROOT / "navi_bench" / "recreation" / "recreation_tasks.csv"


def test_recreation_tasks_csv_has_25_unique_tasks():
    with TASKS_CSV.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 25

    task_ids = [row["task_id"] for row in rows]
    assert len(task_ids) == len(set(task_ids))
    assert task_ids[0] == "navi_bench/recreation/filters/0"


def test_recreation_tasks_instantiate_with_recreation_verifier():
    with TASKS_CSV.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    for row in rows:
        dataset_item = DatasetItem.model_validate(row)
        task_config = dataset_item.generate_task_config()
        evaluator = instantiate(task_config.eval_config)

        assert isinstance(evaluator, RecreationUrlMatch)
        assert evaluator.goal_params
        assert task_config.url == "https://www.recreation.gov/search"


def test_demo_recreation_loads_all_scenarios():
    scenarios = load_scenarios() 

    assert len(scenarios) == 25
    assert scenarios[0].task_id == "navi_bench/recreation/filters/0"
    assert scenarios[-1].task_id == "navi_bench/recreation/filters/24"


def test_recreation_tasks_use_updated_sort_encodings_and_new_electrical_hookup():
    with TASKS_CSV.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    allowed_sort_values = {"score", "distance", "average_rating", "price asc", "aggregate_cell_coverage"}
    saw_electrical_hookup = False

    for row in rows[1:]:
        config = json.loads(row["task_generation_config_json"])
        gt_url = config["gt_url"]
        dataset_item = DatasetItem.model_validate(row)
        task_config = dataset_item.generate_task_config()
        evaluator = instantiate(task_config.eval_config)

        if "sort" in evaluator.goal_params:
            assert evaluator.goal_params["sort"] in allowed_sort_values

        if "electrical_hookup=" in gt_url:
            saw_electrical_hookup = True
            assert evaluator.goal_params["electrical_hookup"] == "30 amp"

    assert saw_electrical_hookup
