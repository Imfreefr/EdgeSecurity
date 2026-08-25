# Banco de dados para produção — caminho recomendado

Para colocar o EdgeSecurity em hospedagem, a recomendação é usar **Supabase** para PostgreSQL + autenticação. O site não deve guardar senhas em `localStorage` nem em uma tabela própria.

## 1. Criar o projeto

1. Crie uma conta no Supabase.
2. Crie um novo projeto.
3. Escolha uma região próxima dos usuários/servidor.
4. Abra o SQL Editor.
5. Execute `supabase-schema.sql`.

O Supabase Auth fornece autenticação por e-mail/senha e mantém os dados de autenticação no schema próprio do Auth. As senhas são armazenadas com hash, não como texto puro. Consulte a documentação oficial de Auth e Password Security.

## 2. Primeiro administrador

1. Crie o primeiro usuário pelo Auth do Supabase.
2. Pegue o UUID desse usuário em `Authentication > Users`.
3. Insira o perfil correspondente em `public.profiles`:

```sql
insert into public.profiles (id, nome, cargo, status)
values ('UUID_DO_USUARIO', 'Administrador', 'administrador', 'ativo');
```

Depois, o administrador poderá criar os demais usuários.

## 3. Não coloque a Service Role Key no frontend

Para o administrador criar contas Auth para outras pessoas, use um backend/Edge Function. A `service_role` key tem privilégios elevados e não deve ser exposta no navegador.

O fluxo recomendado é:

```text
Administrador
      ↓
EdgeSecurity frontend
      ↓ JWT do administrador
Backend / Edge Function
      ↓
Supabase Auth Admin API
      ↓
Usuário criado
      ↓
public.profiles + permissões
```

## 4. Login

Troque o login mock atual pelo Supabase Auth. O fluxo de login por e-mail/senha usa `signInWithPassword()`.

O frontend deve guardar apenas a sessão/token administrados pelo SDK. Não armazene a senha do usuário.

## 5. Permissões

`public.profiles.permissoes` contém as permissões funcionais da aplicação. O cargo (`administrador`/`usuario`) é uma camada adicional.

Para segurança real, não confie apenas em esconder botões. O backend e o PostgreSQL devem validar o acesso. O Supabase recomenda Row Level Security (RLS) nas tabelas expostas ao navegador.

## 6. Câmeras

Cada câmera deve existir em `public.cameras`. O vínculo entre usuário e câmera fica em `public.usuario_cameras`.

Para câmera IP/Wi-Fi, prefira armazenar no servidor apenas os metadados e a referência do stream. Não coloque credenciais RTSP no HTML/JavaScript.

## 7. Alertas e IA

Quando o YOLO26 detectar uma situação de risco:

```text
Câmera
  ↓
Backend de IA
  ↓
YOLO26 + rastreamento
  ↓
Motor de risco
  ↓
Evento
  ↓
public.alertas
  ↓
Dashboard / Alertas / Relatórios
```

Não grave todos os frames no banco. Grave eventos, métricas e metadados; se houver necessidade de evidência, use armazenamento de objetos separado.
