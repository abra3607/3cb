"""empty message

Revision ID: cb45e24e9472
Revises: 
Create Date: 2024-10-05 15:24:06.933274

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cb45e24e9472'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('elicitation_snapshots',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('toml_content', sa.String(length=1000000), nullable=False),
    sa.Column('is_most_recent', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('toml_content', name='uc_elicitation_snapshots_toml_content')
    )
    op.create_table('task_config_snapshots',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('name', sa.String(length=1000000), nullable=False),
    sa.Column('toml_content', sa.String(length=1000000), nullable=False),
    sa.Column('is_most_recent', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name', 'toml_content', name='uc_task_config_snapshots_name_toml_content')
    )
    op.create_table('eval_runs_v2',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('task_config_snapshot', sa.Integer(), nullable=False),
    sa.Column('elicitation_snapshot', sa.Integer(), nullable=False),
    sa.Column('model', sa.String(length=1000000), nullable=False),
    sa.Column('status', sa.Enum('RUNNING', 'SUCCESS', 'FAILURE', 'ERROR', 'REFUSED', name='runstatus'), nullable=False),
    sa.Column('exception_stacktrace', sa.String(length=1000000), nullable=True),
    sa.ForeignKeyConstraint(['elicitation_snapshot'], ['elicitation_snapshots.id'], name='fk_eval_runs_v2_elicitation_snapshots_id_elicitation_snapshot', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['task_config_snapshot'], ['task_config_snapshots.id'], name='fk_eval_runs_v2_task_config_snapshots_id_task_config_snapshot', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('chat_messages_v2',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('run', sa.Integer(), nullable=False),
    sa.Column('ordinal', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(length=1000000), nullable=False),
    sa.Column('content', sa.String(length=1000000), nullable=False),
    sa.Column('is_prefilled', sa.Boolean(), nullable=False),
    sa.Column('underlying_communication', sa.String(length=1000000), nullable=True),
    sa.ForeignKeyConstraint(['run'], ['eval_runs_v2.id'], name='fk_chat_messages_v2_eval_runs_v2_id_run', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_messages_v2_run'), 'chat_messages_v2', ['run'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_chat_messages_v2_run'), table_name='chat_messages_v2')
    op.drop_table('chat_messages_v2')
    op.drop_table('eval_runs_v2')
    op.drop_table('task_config_snapshots')
    op.drop_table('elicitation_snapshots')
    # ### end Alembic commands ###
