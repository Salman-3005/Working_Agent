const BASE_URL = '/api';

export async function fetchTenants() {
  const res = await fetch(`${BASE_URL}/tenants`);
  return res.json();
}

export async function fetchStats(tenantId = 'ALL') {
  const url = tenantId !== 'ALL' ? `${BASE_URL}/stats?tenant=${tenantId}` : `${BASE_URL}/stats`;
  const res = await fetch(url);
  return res.json();
}

export async function fetchDisagreements({ tenant = 'ALL', reason = 'ALL', sortOrder = '', search = '' }) {
  const params = new URLSearchParams();
  if (tenant !== 'ALL') params.append('tenant', tenant);
  if (reason !== 'ALL') params.append('reason', reason);
  if (sortOrder) params.append('sort_order', sortOrder);
  if (search) params.append('search', search);

  const res = await fetch(`${BASE_URL}/disagreements?${params.toString()}`);
  return res.json();
}

export async function runImport() {
  const res = await fetch(`${BASE_URL}/import`, { method: 'POST' });
  return res.json();
}

export async function runReconciliation() {
  const res = await fetch(`${BASE_URL}/reconcile`, { method: 'POST' });
  return res.json();
}

export async function runTestSuite() {
  const res = await fetch(`${BASE_URL}/run-tests`, { method: 'POST' });
  return res.json();
}
