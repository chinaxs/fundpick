/** 业务接口定义：按模块拆分，页面只调用这里。 */
import type {
  Article,
  ArticleCreatePayload,
  ArticleListItem,
  ArticleQuery,
  ArticleUpdatePayload,
  ChangePasswordPayload,
  LoginPayload,
  PageResult,
  TokenResponse,
  User,
  UserCreatePayload,
  UserQuery,
  UserUpdatePayload,
} from '@project/shared'

import { api } from './client'

export const authApi = {
  login: (payload: LoginPayload) => api.post<TokenResponse>('/auth/login', payload),
  me: () => api.get<User>('/auth/me'),
  changePassword: (payload: ChangePasswordPayload) =>
    api.post<{ message: string }>('/auth/change-password', payload),
}

export const userApi = {
  list: (params: UserQuery) => api.get<PageResult<User>>('/admin/users', params),
  detail: (id: number) => api.get<User>(`/admin/users/${id}`),
  create: (payload: UserCreatePayload) => api.post<User>('/admin/users', payload),
  update: (id: number, payload: UserUpdatePayload) =>
    api.patch<User>(`/admin/users/${id}`, payload),
  remove: (id: number) => api.delete<{ id: number }>(`/admin/users/${id}`),
}

export const articleApi = {
  list: (params: ArticleQuery) => api.get<PageResult<ArticleListItem>>('/admin/articles', params),
  detail: (id: number) => api.get<Article>(`/admin/articles/${id}`),
  create: (payload: ArticleCreatePayload) => api.post<Article>('/admin/articles', payload),
  update: (id: number, payload: ArticleUpdatePayload) =>
    api.patch<Article>(`/admin/articles/${id}`, payload),
  remove: (id: number) => api.delete<{ id: number }>(`/admin/articles/${id}`),
}
