import { MigrationInterface, QueryRunner } from 'typeorm';

export class CreateLabTestLogs1736122000000 implements MigrationInterface {
  name = 'CreateLabTestLogs1736122000000';

  public async up(queryRunner: QueryRunner): Promise<void> {
    // Create lab_test_logs table
    await queryRunner.query(`
      CREATE TABLE lab_test_logs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        admin_user_id UUID REFERENCES admin_users(id) ON DELETE SET NULL,
        test_type VARCHAR(20) NOT NULL,
        query TEXT NOT NULL,
        parameters JSONB NOT NULL,
        results JSONB NOT NULL,
        search_latency_ms INTEGER,
        rerank_latency_ms INTEGER,
        llm_latency_ms INTEGER,
        total_latency_ms INTEGER,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

        CONSTRAINT chk_lab_test_logs_test_type CHECK (test_type IN ('search', 'generate', 'compare'))
      )
    `);

    // Create indexes
    await queryRunner.query(`CREATE INDEX idx_lab_test_logs_admin_user_id ON lab_test_logs(admin_user_id)`);
    await queryRunner.query(`CREATE INDEX idx_lab_test_logs_test_type ON lab_test_logs(test_type)`);
    await queryRunner.query(`CREATE INDEX idx_lab_test_logs_query ON lab_test_logs(query text_pattern_ops)`);
    await queryRunner.query(`CREATE INDEX idx_lab_test_logs_created_at ON lab_test_logs(created_at)`);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP TABLE IF EXISTS lab_test_logs`);
  }
}
