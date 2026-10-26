export interface UserLogin {
    email: string
    password: string
}

export interface UserCreate {
    email: string
    password: string
}

export interface TokenResponse {
    access_token: string
    token_type: string
}

export interface UserResponse {
    id: number
    email: string
    role: string
}