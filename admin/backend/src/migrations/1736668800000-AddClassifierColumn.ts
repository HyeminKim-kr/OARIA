import { MigrationInterface, QueryRunner } from 'typeorm';

export class AddClassifierColumn1736668800000 implements MigrationInterface {
  name = 'AddClassifierColumn1736668800000';

  public async up(queryRunner: QueryRunner): Promise<void> {
    // Add classifier column to rag_settings
    await queryRunner.query(`
      ALTER TABLE rag_settings
      ADD COLUMN classifier VARCHAR(50) DEFAULT NULL
    `);

    // Update default settings to use pubmedbert classifier
    await queryRunner.query(`
      UPDATE rag_settings
      SET classifier = 'pubmedbert_domain_v1'
      WHERE name = 'default'
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`
      ALTER TABLE rag_settings DROP COLUMN IF EXISTS classifier
    `);
  }
}
