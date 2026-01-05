import { MigrationInterface, QueryRunner } from 'typeorm';

export class InitialAdminSchema1735600000000 implements MigrationInterface {
  name = 'InitialAdminSchema1735600000000';

  public async up(queryRunner: QueryRunner): Promise<void> {
    // Create admin_users table
    await queryRunner.query(`
      CREATE TABLE admin_users (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        email VARCHAR(255) NOT NULL,
        google_id VARCHAR(255) NOT NULL,
        name VARCHAR(255),
        picture VARCHAR(512),
        status VARCHAR(20) NOT NULL DEFAULT 'pending',
        role VARCHAR(50) NOT NULL DEFAULT 'admin',
        approved_by UUID REFERENCES admin_users(id),
        approved_at TIMESTAMPTZ,
        rejected_reason TEXT,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        deactivated_by UUID REFERENCES admin_users(id),
        deactivated_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        last_login_at TIMESTAMPTZ
      )
    `);

    await queryRunner.query(`CREATE UNIQUE INDEX ix_admin_users_email ON admin_users(email)`);
    await queryRunner.query(`CREATE UNIQUE INDEX ix_admin_users_google_id ON admin_users(google_id)`);
    await queryRunner.query(`CREATE INDEX ix_admin_users_status ON admin_users(status)`);
    await queryRunner.query(`CREATE INDEX ix_admin_users_role ON admin_users(role)`);

    // Create admin_refresh_tokens table
    await queryRunner.query(`
      CREATE TABLE admin_refresh_tokens (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        admin_id UUID NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
        token_hash VARCHAR(64) NOT NULL,
        expires_at TIMESTAMPTZ NOT NULL,
        device_info VARCHAR(255),
        ip_address VARCHAR(45),
        revoked_at TIMESTAMPTZ,
        revoked_reason VARCHAR(100),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        last_used_at TIMESTAMPTZ
      )
    `);

    await queryRunner.query(`CREATE INDEX ix_admin_refresh_tokens_admin_id ON admin_refresh_tokens(admin_id)`);
    await queryRunner.query(`CREATE INDEX ix_admin_refresh_tokens_token_hash ON admin_refresh_tokens(token_hash)`);
    await queryRunner.query(`
      CREATE INDEX ix_admin_refresh_tokens_valid
      ON admin_refresh_tokens(admin_id, expires_at)
      WHERE revoked_at IS NULL
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP TABLE IF EXISTS admin_refresh_tokens`);
    await queryRunner.query(`DROP TABLE IF EXISTS admin_users`);
  }
}
