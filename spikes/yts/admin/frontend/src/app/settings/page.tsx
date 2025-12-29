export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="mt-1 text-sm text-gray-500">
          Configure system settings
        </p>
      </div>

      <div className="rounded-lg bg-white p-6 shadow">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">
          System Information
        </h2>
        <dl className="space-y-4">
          <div className="flex justify-between border-b border-gray-100 pb-2">
            <dt className="text-sm text-gray-500">API Endpoint</dt>
            <dd className="text-sm font-medium text-gray-900">
              http://localhost:13000
            </dd>
          </div>
          <div className="flex justify-between border-b border-gray-100 pb-2">
            <dt className="text-sm text-gray-500">Database</dt>
            <dd className="text-sm font-medium text-gray-900">
              PostgreSQL (localhost:15432)
            </dd>
          </div>
          <div className="flex justify-between border-b border-gray-100 pb-2">
            <dt className="text-sm text-gray-500">Object Storage</dt>
            <dd className="text-sm font-medium text-gray-900">
              MinIO (localhost:19000)
            </dd>
          </div>
          <div className="flex justify-between border-b border-gray-100 pb-2">
            <dt className="text-sm text-gray-500">Message Broker</dt>
            <dd className="text-sm font-medium text-gray-900">
              Redis (localhost:16379)
            </dd>
          </div>
        </dl>
      </div>

      <div className="rounded-lg bg-white p-6 shadow">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">
          Rate Limiting
        </h2>
        <dl className="space-y-4">
          <div className="flex justify-between border-b border-gray-100 pb-2">
            <dt className="text-sm text-gray-500">Europe PMC API</dt>
            <dd className="text-sm font-medium text-gray-900">
              10 req/sec (burst: 20)
            </dd>
          </div>
          <div className="flex justify-between border-b border-gray-100 pb-2">
            <dt className="text-sm text-gray-500">Concurrent Downloads</dt>
            <dd className="text-sm font-medium text-gray-900">5</dd>
          </div>
          <div className="flex justify-between border-b border-gray-100 pb-2">
            <dt className="text-sm text-gray-500">Circuit Breaker</dt>
            <dd className="text-sm font-medium text-green-600">Closed</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
