-- EdgeSecurity / Supabase
-- Senhas NÃO devem ser armazenadas nesta base. O Supabase Auth cuida delas.

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  nome text not null,
  cargo text not null default 'usuario' check (cargo in ('administrador','usuario')),
  status text not null default 'ativo' check (status in ('ativo','inativo','bloqueado')),
  permissoes jsonb not null default '{"visualizar_cameras":true,"usar_camera_dispositivo":true,"gerenciar_cameras":false,"visualizar_alertas":true,"visualizar_relatorios":true,"gerenciar_usuarios":false,"gerenciar_permissoes":false,"acessar_configuracoes":true}'::jsonb,
  ultimo_login timestamptz,
  ultimo_logout timestamptz,
  criado_em timestamptz not null default now()
);

create table if not exists public.cameras (
  id uuid primary key default gen_random_uuid(),
  nome text not null,
  tipo text not null default 'browser',
  endereco_stream text,
  localizacao text,
  status text not null default 'ativo' check (status in ('ativo','inativo','offline')),
  criado_por uuid references public.profiles(id),
  criado_em timestamptz not null default now()
);

create table if not exists public.usuario_cameras (
  usuario_id uuid not null references public.profiles(id) on delete cascade,
  camera_id uuid not null references public.cameras(id) on delete cascade,
  primary key (usuario_id, camera_id)
);

create table if not exists public.alertas (
  id uuid primary key default gen_random_uuid(),
  camera_id uuid references public.cameras(id) on delete set null,
  tipo text not null,
  nivel text not null check (nivel in ('safe','medium','high','critical')),
  descricao text,
  data_hora timestamptz not null default now(),
  status text not null default 'aberto' check (status in ('aberto','reconhecido','resolvido')),
  dados jsonb not null default '{}'::jsonb
);

create table if not exists public.atividades (
  id bigint generated always as identity primary key,
  usuario_id uuid references public.profiles(id) on delete set null,
  acao text not null,
  descricao text,
  data_hora timestamptz not null default now(),
  dados jsonb not null default '{}'::jsonb
);

alter table public.profiles enable row level security;
alter table public.cameras enable row level security;
alter table public.usuario_cameras enable row level security;
alter table public.alertas enable row level security;
alter table public.atividades enable row level security;

-- Usuário pode ler o próprio perfil.
create policy "profiles own read" on public.profiles for select to authenticated using (id = auth.uid());

-- Usuário pode atualizar somente dados não administrativos do próprio perfil.
create policy "profiles own update" on public.profiles for update to authenticated using (id = auth.uid()) with check (id = auth.uid());

-- A gestão administrativa deve ser feita pelo backend/Edge Function com service role.
-- NÃO coloque a service_role key no JavaScript do navegador.

create policy "users read assigned cameras" on public.cameras for select to authenticated
using (
  exists (select 1 from public.usuario_cameras uc where uc.camera_id = cameras.id and uc.usuario_id = auth.uid())
  or exists (select 1 from public.profiles p where p.id = auth.uid() and p.cargo = 'administrador')
);

create policy "users read own camera assignments" on public.usuario_cameras for select to authenticated
using (usuario_id = auth.uid());

create policy "users read own alerts" on public.alertas for select to authenticated
using (
  exists (select 1 from public.usuario_cameras uc where uc.camera_id = alertas.camera_id and uc.usuario_id = auth.uid())
  or exists (select 1 from public.profiles p where p.id = auth.uid() and p.cargo = 'administrador')
);

create policy "users read own activities" on public.atividades for select to authenticated
using (usuario_id = auth.uid() or exists (select 1 from public.profiles p where p.id = auth.uid() and p.cargo = 'administrador'));
