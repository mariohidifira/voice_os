export type Role="owner"|"admin"|"operator"|"viewer";
export interface ApiError{error:{code:string;message:string;details:Record<string,unknown>;request_id:string}}
export interface Session{session_id:string;call_id:string;livekit_url:string;token:string;expires_at:string}
export type { components, operations, paths } from "./openapi";
