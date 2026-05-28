import { createClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL as string
const key = import.meta.env.VITE_SUPABASE_KEY as string

if (!url || !key) {
  throw new Error(
    'Supabase nao configurado. Defina VITE_SUPABASE_URL e VITE_SUPABASE_KEY em dashboard/.env.local',
  )
}

export const supabase = createClient(url, key)