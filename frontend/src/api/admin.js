import request from './request'

// 修改申请
export function submitModRequest(data) {
  return request.post('/mod-requests', data)
}

export function listModRequests(params) {
  return request.get('/admin/mod-requests', { params })
}

export function getModRequest(id) {
  return request.get(`/admin/mod-requests/${id}`)
}

export function reviewModRequest(id, data) {
  return request.post(`/admin/mod-requests/${id}/review`, data)
}

// 流量监控
export function getTrafficRecent(params) {
  return request.get('/admin/traffic/recent', { params })
}

export function getTrafficSummary(params) {
  return request.get('/admin/traffic/summary', { params })
}

// 用户管理
export function listAdminUsers(params) {
  return request.get('/admin/users', { params })
}

export function updateAdminUser(id, data) {
  return request.patch(`/admin/users/${id}`, data)
}

export function resetAdminUserPassword(id, new_password) {
  return request.post(`/admin/users/${id}/reset_password`, { new_password })
}

export function deleteAdminUser(id) {
  return request.delete(`/admin/users/${id}`)
}

export function getAdminStats() {
  return request.get('/admin/stats')
}

// 高级可视化分析
export function getAnalyticsHeatmap(params) {
  return request.get('/admin/analytics/heatmap', { params })
}

export function getAnalyticsUserActivity(params) {
  return request.get('/admin/analytics/user-activity', { params })
}

export function getAnalyticsAuditStats(params) {
  return request.get('/admin/analytics/audit-stats', { params })
}

export function getAnalyticsDbChanges(params) {
  return request.get('/admin/analytics/db-changes', { params })
}

export function getAnalyticsEndpointHealth(params) {
  return request.get('/admin/analytics/endpoint-health', { params })
}
