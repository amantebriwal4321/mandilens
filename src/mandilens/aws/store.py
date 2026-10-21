"""Lot storage. Memory locally, DynamoDB when LOTS_TABLE is set."""

from __future__ import annotations

import os
from decimal import Decimal


class MemoryStore:
    def __init__(self) -> None:
        self.lots: dict[str, dict] = {}

    def put(self, lot: dict) -> None:
        self.lots[lot["lot_id"]] = lot

    def get(self, lot_id: str) -> dict | None:
        return self.lots.get(lot_id)

    def clear(self) -> None:
        self.lots.clear()


class DynamoStore:
    def __init__(self, table_name: str, table=None) -> None:
        if table is None:
            import boto3

            table = boto3.resource("dynamodb").Table(table_name)
        self.table = table

    def put(self, lot: dict) -> None:
        item = {key: value for key, value in lot.items() if key not in {"preview_jpeg", "rectified_jpeg"}}
        self.table.put_item(Item=_to_decimal(item))

    def get(self, lot_id: str) -> dict | None:
        response = self.table.get_item(Key={"lot_id": lot_id})
        item = response.get("Item")
        if item is None:
            return None
        return _from_decimal(item)

    def clear(self) -> None:
        return None


def _to_decimal(value):
    if isinstance(value, float):
        return Decimal(str(round(value, 4)))
    if isinstance(value, dict):
        return {key: _to_decimal(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [_to_decimal(item) for item in value]
    return value


def _from_decimal(value):
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, dict):
        return {key: _from_decimal(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_from_decimal(item) for item in value]
    return value


def lot_store() -> MemoryStore | DynamoStore:
    table = os.environ.get("LOTS_TABLE", "").strip()
    if table:
        return DynamoStore(table)
    return MemoryStore()
