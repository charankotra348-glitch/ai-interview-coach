"""adaptive questions: difficulty, rationale and follow-up target

Revision ID: c4e8a2f61b07
Revises: 7bf3fb5df5da
Create Date: 2026-10-13

Written by hand: autogenerate does not detect CHECK constraints.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4e8a2f61b07"
down_revision: Union[str, Sequence[str], None] = "7bf3fb5df5da"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("questions", sa.Column("difficulty", sa.Integer(), server_default="2", nullable=False))
    op.add_column("questions", sa.Column("rationale", sa.String(length=200), nullable=True))
    op.add_column("questions", sa.Column("target_criterion", sa.String(length=60), nullable=True))
    op.create_check_constraint(op.f("ck_questions_difficulty_range"), "questions",
                               "difficulty BETWEEN 1 AND 3")
    op.create_check_constraint(op.f("ck_questions_follow_up_has_target"), "questions",
                               "(parent_question_id IS NULL) = (target_criterion IS NULL)")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_questions_follow_up_has_target"), "questions", type_="check")
    op.drop_constraint(op.f("ck_questions_difficulty_range"), "questions", type_="check")
    op.drop_column("questions", "target_criterion")
    op.drop_column("questions", "rationale")
    op.drop_column("questions", "difficulty")