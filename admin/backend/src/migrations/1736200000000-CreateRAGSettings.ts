import { MigrationInterface, QueryRunner } from 'typeorm';

export class CreateRAGSettings1736200000000 implements MigrationInterface {
  name = 'CreateRAGSettings1736200000000';

  public async up(queryRunner: QueryRunner): Promise<void> {
    // Create rag_settings table
    await queryRunner.query(`
      CREATE TABLE rag_settings (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(50) NOT NULL UNIQUE,
        description TEXT,
        chunker VARCHAR(50) NOT NULL DEFAULT 'semantic',
        embedder VARCHAR(50) NOT NULL DEFAULT 'openai',
        retriever VARCHAR(50) NOT NULL DEFAULT 'hybrid',
        reranker VARCHAR(50),
        parameters JSONB,
        is_active BOOLEAN NOT NULL DEFAULT false,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
      )
    `);

    // Create index for active settings lookup
    await queryRunner.query(`
      CREATE INDEX idx_rag_settings_is_active ON rag_settings(is_active) WHERE is_active = true
    `);

    // Insert default settings
    await queryRunner.query(`
      INSERT INTO rag_settings (name, description, chunker, embedder, retriever, reranker, parameters, is_active)
      VALUES (
        'default',
        '기본 RAG 설정',
        'semantic',
        'openai',
        'hybrid',
        'bge',
        '{"limit": 10, "alpha": 0.7}'::jsonb,
        true
      )
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP TABLE IF EXISTS rag_settings`);
  }
}
