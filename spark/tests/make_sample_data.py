"""Deterministic SYNTHETIC data in the Instacart schema, for tests only.

Nothing generated here resembles real Instacart figures and no number from it may appear
in a README, resume bullet or memo. Its job is to give the dbt models and the PySpark
ports the same small input so their outputs can be compared row for row.

Shape guarantees chosen to exercise every code path:
  * every customer has between 4 and 30 orders (so cohort retention reaches index 20 and,
    as in the real extract, no customer has fewer than 4)
  * a customer's last order is 'train' or 'test'; 'test' orders have no line items
  * the first order of each customer has a null days_since_prior_order
  * product popularity is skewed so some pairs co-occur often enough to clear the
    (shrunken) affinity thresholds the tests pass in
  * the 7 x 24 grid is NOT fully populated, so empty slots stay empty
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

DEPARTMENTS = ["produce", "dairy eggs", "pantry", "beverages", "snacks", "frozen"]
N_AISLES = 14
N_PRODUCTS = 150


def generate(out_dir: Path, users: int = 300, seed: int = 7) -> dict[str, int]:
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)

    departments = [(i + 1, name) for i, name in enumerate(DEPARTMENTS)]
    aisles = [(i + 1, f"aisle {i + 1:02d}") for i in range(N_AISLES)]
    aisle_dept = {a_id: 1 + (a_id - 1) % len(DEPARTMENTS) for a_id, _ in aisles}
    products = []
    for p_id in range(1, N_PRODUCTS + 1):
        aisle_id = 1 + (p_id - 1) % N_AISLES
        # embedded comma and quote exercise the CSV quoting path
        name = f'Product {p_id}, "{rng.choice(["Org", "Std", "Prem"])}"' if p_id % 17 == 0 else f"Product {p_id}"
        products.append((p_id, name, aisle_id, aisle_dept[aisle_id]))

    weights = [1.0 / (rank ** 0.8) for rank in range(1, N_PRODUCTS + 1)]
    product_ids = list(range(1, N_PRODUCTS + 1))

    orders, lines = [], []
    order_id = 1000
    for user_id in range(1, users + 1):
        n_orders = rng.randint(4, 30)
        favourites = rng.sample(product_ids, 12)
        for order_number in range(1, n_orders + 1):
            order_id += rng.randint(1, 5)
            if order_number == n_orders:
                eval_set = rng.choice(["train", "test"])
            else:
                eval_set = "prior"
            dow = rng.choice([0, 1, 1, 2, 3, 4, 4, 5, 6])
            hour = rng.choice([8, 9, 10, 10, 11, 13, 14, 15, 16, 17, 20])
            days = "" if order_number == 1 else float(rng.randint(0, 30))
            orders.append((order_id, user_id, eval_set, order_number, dow, hour, days))
            if eval_set == "test":
                continue
            basket = set(rng.sample(favourites, rng.randint(0, 4)))
            while len(basket) < rng.randint(2, 14):
                basket.add(rng.choices(product_ids, weights)[0])
            basket_list = list(basket)
            rng.shuffle(basket_list)
            for cart_pos, product_id in enumerate(basket_list, start=1):
                reordered = int(product_id in favourites and rng.random() < 0.8) or int(rng.random() < 0.2)
                lines.append((order_id, product_id, cart_pos, reordered))

    def write(name: str, header: list[str], rows: list[tuple]) -> None:
        with (out_dir / f"{name}.csv").open("w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            writer.writerows(rows)

    write("departments", ["department_id", "department"], departments)
    write("aisles", ["aisle_id", "aisle"], aisles)
    write("products", ["product_id", "product_name", "aisle_id", "department_id"], products)
    write(
        "orders",
        ["order_id", "user_id", "eval_set", "order_number", "order_dow", "order_hour_of_day", "days_since_prior_order"],
        orders,
    )
    write("order_products", ["order_id", "product_id", "add_to_cart_order", "reordered"], lines)
    return {"orders": len(orders), "order_products": len(lines), "users": users}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--users", type=int, default=300)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    print(generate(args.out_dir, args.users, args.seed))
