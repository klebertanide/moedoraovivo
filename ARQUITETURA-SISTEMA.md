# MOEDOR AO VIVO - Arquitetura do Sistema

## Visão Geral

O projeto MOEDOR AO VIVO é uma plataforma interativa complexa para lives de humor no YouTube que integra múltiplas funcionalidades em tempo real. O sistema será desenvolvido em Python usando Flask como framework principal, com WebSockets para comunicação em tempo real e integração com diversas APIs externas.

## Arquitetura Geral

### Stack Tecnológico
- **Backend**: Flask (Python 3.11+)
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla + WebSockets)
- **Banco de Dados**: SQLite (desenvolvimento) / PostgreSQL (produção)
- **Comunicação em Tempo Real**: Flask-SocketIO
- **Processamento de Áudio**: OpenAI Whisper
- **Processamento de Vídeo**: OpenCV
- **APIs Externas**: Hotmart, ElevenLabs, Mercado Pago, OpenAI

### Componentes Principais

#### 1. Sistema de Autenticação
- **Webhook Hotmart**: Recebe notificações de novos assinantes
- **Sessões**: Controle de usuários logados
- **Middleware**: Verificação de acesso a áreas restritas

#### 2. Interface do Usuário
- **Página Principal**: Embed YouTube + câmeras extras
- **Big Brother Moído**: Visualização em mosaico das câmeras RTSP
- **Sistema de Mensagens**: Formulário simples com rate limiting
- **Botões de Interação**: Vergonha alheia, doações, etc.

#### 3. Sistema de Mensagens em Tempo Real
- **WebSockets**: Comunicação bidirecional
- **Fila de Mensagens**: Controle de exibição no OBS
- **Sistema de Likes**: Votação em mensagens
- **Rate Limiting**: Prevenção de flood

#### 4. Integrações de IA e Áudio
- **Whisper**: Transcrição contínua da live
- **ElevenLabs**: Síntese de voz para vergonha alheia
- **Análise de Sentimento**: Detecção de momentos polêmicos
- **Geração de Enquetes**: Baseada na transcrição

#### 5. Processamento de Vídeo
- **OpenCV**: Detecção facial e captura de frames
- **IA de Expressões**: Exagero de caras engraçadas
- **Mural Automático**: Atualização em tempo real

#### 6. Sistema de Pagamentos
- **Mercado Pago**: Processamento de doações
- **Vergonha Alheia**: Cobrança de R$ 20,00
- **Aviãozinho**: Sistema de doações livres

#### 7. Painel Administrativo
- **Dashboard**: Estatísticas em tempo real
- **Gerenciamento**: Conteúdo, câmeras, configurações
- **Controles**: Geração de eventos fictícios

#### 8. Overlays para OBS
- **QR Code**: Constante para adesão
- **Mensagens**: Design glitch/grunge
- **Boas-vindas**: Animações com berinjelas
- **Doações**: Chuva de emojis de dinheiro

## Fluxo de Dados

### 1. Autenticação e Acesso
```
Usuário → Hotmart Webhook → Verificação → Sessão → Acesso à Plataforma
```

### 2. Mensagens dos Usuários
```
Formulário → Rate Limiting → Banco de Dados → WebSocket → Fila OBS → Overlay
```

### 3. Vergonha Alheia
```
Botão → Pagamento (R$ 20) → Fila (máx 3) → Seleção Aleatória → ElevenLabs → Áudio → Overlay
```

### 4. Transcrição e Análise
```
Áudio Live → Whisper (15min) → Análise Polêmica → Geração Enquete → Exibição
```

### 5. Detecção Facial
```
Stream Câmeras → OpenCV → Detecção Face → IA Exagero → Mural Caras
```

## Banco de Dados

### Tabelas Principais

#### users
- id (PK)
- hotmart_id
- name
- email
- created_at
- last_login
- is_active

#### messages
- id (PK)
- user_id (FK)
- fake_name
- content
- likes_count
- created_at
- displayed_at
- is_displayed

#### embarrassing_truths
- id (PK)
- content
- target_member
- created_by (FK)
- created_at
- is_active

#### welcome_messages
- id (PK)
- template
- created_by (FK)
- created_at
- is_active

#### polls
- id (PK)
- question
- option_a
- option_b
- votes_a
- votes_b
- created_at
- ends_at
- is_active

#### donations
- id (PK)
- user_id (FK)
- amount
- payment_id
- status
- created_at

#### transcriptions
- id (PK)
- content
- start_time
- end_time
- polemic_score
- created_at

#### cameras
- id (PK)
- name
- rtsp_url
- is_active
- position_x
- position_y

## Sistemas de Fila

### 1. Fila de Overlays OBS
- **Prioridade**: Boas-vindas > Vergonha > Mensagens > Doações
- **Timing**: Configurável por tipo
- **Conflitos**: Sistema de espera inteligente

### 2. Fila de Vergonha Alheia
- **Limite**: 3 por live
- **Pagamento**: Verificação antes da execução
- **Seleção**: Completamente aleatória

### 3. Fila de Mensagens
- **Rate Limiting**: Por usuário e global
- **Ordenação**: Por likes e timestamp
- **Exibição**: Sequencial com timing

## Configurações e Timers

### Timers Configuráveis
- **Mensagens**: Tempo na tela, fade out, delay
- **Boas-vindas**: Duração animação, delay berinjelas
- **Vergonha**: Tempo de exibição do texto
- **Doações**: Duração chuva de emojis
- **Enquetes**: Tempo de votação (padrão 10min)

### Rate Limiting
- **Mensagens**: 1 por minuto por usuário
- **Vergonha**: 1 por usuário por live
- **Doações**: Sem limite
- **Likes**: 10 por minuto por usuário

## Segurança e Performance

### Segurança
- **Autenticação**: Webhook Hotmart verificado
- **Sanitização**: Todas as entradas de usuário
- **Rate Limiting**: Proteção contra abuse
- **Validação**: Pagamentos e transações

### Performance
- **Cache**: Dados frequentes em memória
- **Processamento Assíncrono**: Whisper, IA, etc.
- **Otimização**: Queries de banco de dados
- **Monitoramento**: Logs e métricas

## Integrações Externas

### Hotmart
- **Webhook**: Notificações de assinatura
- **Verificação**: Status de assinante ativo
- **Dados**: Nome, email, data de assinatura

### ElevenLabs
- **API**: v2.5
- **Voice ID**: CY9SQTU8fYN5MZMw15Ma
- **Limite**: Conforme plano de assinatura
- **Formato**: MP3 para reprodução

### Mercado Pago
- **API**: Pagamentos e doações
- **Webhook**: Confirmação de pagamentos
- **Valores**: R$ 20,00 (vergonha) + valores livres

### OpenAI
- **Whisper**: Transcrição local
- **GPT**: Análise de sentimento e geração de conteúdo
- **Limites**: Conforme plano de assinatura

## Considerações Técnicas

### Processamento Local
- **Whisper**: Modelo local para reduzir custos
- **OpenCV**: Processamento de vídeo local
- **Cache**: Dados frequentes em memória

### Escalabilidade
- **WebSockets**: Suporte a múltiplos usuários
- **Filas**: Processamento assíncrono
- **Banco**: Otimizado para consultas frequentes

### Monitoramento
- **Logs**: Todas as ações importantes
- **Métricas**: Performance e uso
- **Alertas**: Falhas e problemas

Esta arquitetura fornece uma base sólida para o desenvolvimento do sistema MOEDOR AO VIVO, garantindo escalabilidade, performance e uma experiência rica para os usuários.

