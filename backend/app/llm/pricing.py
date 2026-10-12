from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, Field

from app.llm.types import NO_COST, Cost, Usage

PRICES_FILE = Path(__file__).with_name("prices.json")


class ModelPrice(BaseModel):
    input_per_million: Decimal
    output_per_million: Decimal


class PriceTable(BaseModel):
    version: str = Field(max_length=20)   # the date prices were checked
    models: dict[str, ModelPrice]

    def estimate(self, model: str, usage: Usage) -> Cost:
        price = self.models.get(model)
        if usage.source != "provider" or price is None:
            return NO_COST
        usd = (
            Decimal(usage.input_tokens) * price.input_per_million
            + Decimal(usage.output_tokens) * price.output_per_million
        ) / Decimal(1_000_000)
        return Cost(
            usd=usd.quantize(Decimal("0.000001")),
            basis="price_table_estimate",
            price_table_version=self.version,
        )


def load_price_table(path: Path = PRICES_FILE) -> PriceTable:
    return PriceTable.model_validate_json(path.read_text())