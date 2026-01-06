import { MigrationInterface, QueryRunner } from 'typeorm';

export class CreateLabFeedbacks1736121600000 implements MigrationInterface {
  name = 'CreateLabFeedbacks1736121600000';

  public async up(queryRunner: QueryRunner): Promise<void> {
    // Create lab_feedbacks table
    await queryRunner.query(`
      CREATE TABLE lab_feedbacks (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        admin_user_id UUID REFERENCES admin_users(id) ON DELETE SET NULL,
        test_type VARCHAR(20) NOT NULL,
        query TEXT NOT NULL,
        rating VARCHAR(10) NOT NULL,
        comment TEXT,
        parameters JSONB NOT NULL,
        result_summary JSONB,
        search_latency_ms INTEGER,
        rerank_latency_ms INTEGER,
        llm_latency_ms INTEGER,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

        CONSTRAINT chk_lab_feedbacks_test_type CHECK (test_type IN ('search', 'generate')),
        CONSTRAINT chk_lab_feedbacks_rating CHECK (rating IN ('good', 'bad'))
      )
    `);

    // Create indexes
    await queryRunner.query(`CREATE INDEX idx_lab_feedbacks_admin_user_id ON lab_feedbacks(admin_user_id)`);
    await queryRunner.query(`CREATE INDEX idx_lab_feedbacks_test_type ON lab_feedbacks(test_type)`);
    await queryRunner.query(`CREATE INDEX idx_lab_feedbacks_rating ON lab_feedbacks(rating)`);
    await queryRunner.query(`CREATE INDEX idx_lab_feedbacks_created_at ON lab_feedbacks(created_at)`);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP TABLE IF EXISTS lab_feedbacks`);
  }
}
