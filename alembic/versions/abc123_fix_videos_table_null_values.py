# First, create a new migration to fix the existing data issue
# Run: alembic revision --autogenerate -m "fix_videos_table_null_values"

"""Fix videos table null values before adding constraints

Revision ID: fix_videos_null_values
Revises: previous_revision_id
Create Date: 2025-07-10 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column

# revision identifiers
revision = 'fix_videos_null_values'
down_revision = 'previous_revision_id'  # Replace with your actual previous revision
branch_labels = None
depends_on = None

def upgrade():
    # Create a temporary table reference for bulk updates
    videos_table = table('videos',
        column('id', sa.Integer),
        column('url', sa.String),
        column('status', sa.String),
        column('background_type', sa.String),
        column('background_url', sa.String),
        column('original_video_url', sa.String)
    )
    
    # Fix any NULL values in the videos table before adding constraints
    
    # 1. Update NULL urls with a default value or remove rows
    # Option A: Set default URL for videos without URL
    op.execute(
        videos_table.update()
        .where(videos_table.c.url.is_(None))
        .values(url='placeholder_url_to_be_updated')
    )
    
    # Option B: Alternatively, delete rows with NULL urls if they're invalid
    # op.execute(videos_table.delete().where(videos_table.c.url.is_(None)))
    
    # 2. Set default values for other potentially NULL columns
    op.execute(
        videos_table.update()
        .where(videos_table.c.status.is_(None))
        .values(status='pending')
    )
    
    op.execute(
        videos_table.update()
        .where(videos_table.c.background_type.is_(None))
        .values(background_type='original')
    )
    
    # 3. Now add the NOT NULL constraints
    op.alter_column('videos', 'url', nullable=False)
    op.alter_column('videos', 'status', nullable=False)
    op.alter_column('videos', 'background_type', nullable=False)
    
    # 4. Add new premium tables
    op.create_table('user_subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('subscription_type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('trial_start_date', sa.DateTime(), nullable=True),
        sa.Column('trial_end_date', sa.DateTime(), nullable=True),
        sa.Column('subscription_start_date', sa.DateTime(), nullable=True),
        sa.Column('subscription_end_date', sa.DateTime(), nullable=True),
        sa.Column('stripe_customer_id', sa.String(), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('premium_features',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('feature_key', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('user_backgrounds',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('background_type', sa.String(), nullable=False),
        sa.Column('cloudinary_url', sa.String(), nullable=False),
        sa.Column('cloudinary_public_id', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('background_replacement_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('video_id', sa.Integer(), nullable=False),
        sa.Column('background_id', sa.Integer(), nullable=True),
        sa.Column('background_prompt', sa.Text(), nullable=True),
        sa.Column('stock_image_url', sa.String(), nullable=True),
        sa.Column('job_status', sa.String(), nullable=False),
        sa.Column('heygen_job_id', sa.String(), nullable=True),
        sa.Column('result_video_url', sa.String(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['background_id'], ['user_backgrounds.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add indexes for better performance
    op.create_index('idx_user_subscriptions_user_id', 'user_subscriptions', ['user_id'])
    op.create_index('idx_user_subscriptions_status', 'user_subscriptions', ['status'])
    op.create_index('idx_user_backgrounds_user_id', 'user_backgrounds', ['user_id'])
    op.create_index('idx_background_jobs_user_id', 'background_replacement_jobs', ['user_id'])
    op.create_index('idx_background_jobs_status', 'background_replacement_jobs', ['job_status'])
    
    # Insert default premium features
    op.execute("""
        INSERT INTO premium_features (name, description, feature_key, is_active, created_at)
        VALUES 
        ('Background Replacement', 'Replace video backgrounds with custom images or AI-generated backgrounds', 'background_replacement', true, NOW()),
        ('Custom Backgrounds', 'Upload and use custom background images', 'custom_backgrounds', true, NOW()),
        ('AI Background Generation', 'Generate backgrounds using AI prompts', 'ai_backgrounds', true, NOW()),
        ('Stock Image Search', 'Search and use stock images as backgrounds', 'stock_images', true, NOW()),
        ('Unlimited Videos', 'Generate unlimited videos per month', 'unlimited_videos', true, NOW())
    """)

def downgrade():
    # Drop the new tables
    op.drop_table('background_replacement_jobs')
    op.drop_table('user_backgrounds')
    op.drop_table('premium_features')
    op.drop_table('user_subscriptions')
    
    # Remove NOT NULL constraints (if needed for rollback)
    op.alter_column('videos', 'url', nullable=True)
    op.alter_column('videos', 'status', nullable=True)
    op.alter_column('videos', 'background_type', nullable=True)
