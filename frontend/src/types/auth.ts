export interface AuthUser {
  id: string;
  email: string;
  display_name?: string | null;
  avatar_url?: string | null;
  oauth_provider?: "google" | "github" | null;
  created_at?: string | null;
}

export interface AuthTokens {
  access_token: string;
  expires_in?: number;
}

export interface EmailCredentials {
  email: string;
  password: string;
}

export interface RegistrationDetails extends EmailCredentials {
  display_name: string;
}
