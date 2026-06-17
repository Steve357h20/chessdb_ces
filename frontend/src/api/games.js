import request from './request'

export function getGames(params) {
  return request.get('/games', { params })
}

export function getGameFilters() {
  return request.get('/games/filters')
}

export function getGame(id) {
  return request.get(`/games/${id}`)
}

export function uploadGames(files) {
  const formData = new FormData()
  if (Array.isArray(files)) {
    files.forEach((file) => formData.append('files', file))
  } else {
    formData.append('files', files)
  }
  return request.post('/games/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function updateGame(id, data) {
  return request.put(`/games/${id}`, data)
}

export function deleteGame(id, force = false) {
  const params = force ? { force: 'true' } : {}
  return request.delete(`/games/${id}`, { params })
}

export function analyzeGame(id, params) {
  return request.post(`/games/${id}/analyze`, params)
}

export function getGameMoves(id) {
  return request.get(`/games/${id}/moves`)
}

export function getGameAnalysis(id) {
  return request.get(`/games/${id}/analysis`)
}
