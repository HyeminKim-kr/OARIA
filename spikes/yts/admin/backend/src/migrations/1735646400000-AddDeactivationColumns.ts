import { MigrationInterface, QueryRunner } from 'typeorm';

export class AddDeactivationColumns1735646400000 implements MigrationInterface {
  name = 'AddDeactivationColumns1735646400000';

  public async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`
      ALTER TABLE admin_users
      ADD COLUMN IF NOT EXISTS deactivated_by UUID REFERENCES admin_users(id),
      ADD COLUMN IF NOT EXISTS deactivated_at TIMESTAMPTZ
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`
      ALTER TABLE admin_users
      DROP COLUMN IF EXISTS deactivated_at,
      DROP COLUMN IF EXISTS deactivated_by
    `);
  }
}
