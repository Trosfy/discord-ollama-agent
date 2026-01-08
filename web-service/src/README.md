# SOLID Architecture - Source Code Structure

This directory contains the frontend source code organized using SOLID principles and Clean Architecture patterns.

## Architecture Layers

### 1. Domain Layer (`domain/`)
**Purpose**: Core business entities, interfaces, and types. No dependencies on external frameworks.

- **`entities/`**: Domain entities (User, Conversation, Model)
  - Pure TypeScript objects/interfaces
  - Business logic that doesn't depend on infrastructure

- **`interfaces/`**: Service contracts (IAuthService, IChatService, IAdminService)
  - Defines what services must do
  - Implementations live in infrastructure layer

- **`types/`**: Shared types (ApiResponse, ErrorTypes)
  - Generic types used across the application

### 2. Application Layer (`application/`)
**Purpose**: Use cases and business logic orchestration. Depends on domain layer only.

- **`use-cases/`**: Business logic orchestration
  - `auth/`: LoginUseCase, LogoutUseCase
  - `chat/`: SendMessageUseCase, RegenerateUseCase
  - `admin/`: LoadModelUseCase, GetVRAMStatsUseCase
  - Each use case is a single business operation

- **`dto/`**: Data Transfer Objects
  - Request/response objects for use cases
  - Validation logic

### 3. Infrastructure Layer (`infrastructure/`)
**Purpose**: External dependencies and implementations. Implements domain interfaces.

- **`api/`**: HTTP API clients (implements domain interfaces)
  - `HttpClient.ts`: Axios instance configuration
  - `AuthApiService.ts`: Implements IAuthService
  - `ChatApiService.ts`: Implements IChatService
  - `AdminApiService.ts`: Implements IAdminService

- **`sse/`**: Server-Sent Events clients
  - `MonitoringSSE.ts`: Real-time monitoring updates

- **`websocket/`**: WebSocket clients
  - `ChatWebSocket.ts`: Real-time chat streaming

- **`storage/`**: Browser storage
  - `LocalStorage.ts`: Persistent storage wrapper

### 4. Presentation Layer (`presentation/`)
**Purpose**: UI components, hooks, and state management. Depends on application layer.

- **`components/`**: React components
  - `ui/`: shadcn/ui base components
  - `layout/`: Layout components (Sidebar, TopBar, MobileNav)
  - `chat/`: Chat-specific components
  - `admin/`: Admin-specific components
  - `providers/`: Context providers

- **`hooks/`**: Custom React hooks
  - `useAuth.ts`: Authentication state
  - `useChat.ts`: Chat functionality
  - `useMonitoring.ts`: Real-time monitoring (SSE)
  - `useTheme.ts`: Theme management

- **`stores/`**: State management (Zustand)
  - `authStore.ts`: Authentication state
  - `chatStore.ts`: Chat state
  - `themeStore.ts`: Theme state

- **`styles/`**: Component-specific styles

### 5. Config Layer (`config/`)
**Purpose**: Application configuration and constants.

- `api.config.ts`: API endpoints and settings
- `constants.ts`: App-wide constants
- `theme.config.ts`: Theme configuration (if needed)

## Dependency Flow

```
presentation → application → domain
     ↓             ↓
infrastructure → domain
```

- **Domain** has no dependencies
- **Application** depends on domain only
- **Infrastructure** depends on domain (implements interfaces)
- **Presentation** depends on application and infrastructure

## SOLID Principles Applied

1. **Single Responsibility Principle (SRP)**
   - Each module has one reason to change
   - Use cases handle one business operation
   - Services handle one type of functionality

2. **Open/Closed Principle (OCP)**
   - Extend via composition, not modification
   - New features = new use cases, not modified ones

3. **Liskov Substitution Principle (LSP)**
   - Interfaces define contracts
   - Implementations can be swapped without breaking code

4. **Interface Segregation Principle (ISP)**
   - Small, focused interfaces
   - IAuthService, IChatService, IAdminService (not one big IService)

5. **Dependency Inversion Principle (DIP)**
   - Depend on abstractions (interfaces), not concretions
   - Infrastructure implements domain interfaces
   - Application uses interfaces, not concrete implementations

## Benefits

1. **Easy to Test**
   - Mock interfaces in tests
   - No dependencies on Next.js or React in business logic

2. **Easy to Swap Implementations**
   - Change API client without changing use cases
   - Switch from polling to WebSocket without changing components

3. **Easy to Understand**
   - Clear separation of concerns
   - Each layer has a single purpose

4. **Easy to Extend**
   - Add new use cases without modifying existing code
   - Add new API services by implementing interfaces

5. **Framework Independent**
   - Core business logic doesn't depend on Next.js
   - Can migrate to different framework without rewriting logic

## Example: Adding a New Feature

**Scenario**: Add "Save Conversation" feature

1. **Domain Layer**:
   ```typescript
   // domain/interfaces/IChatService.ts
   export interface IChatService {
     // ... existing methods
     saveConversation(conversationId: string, title: string): Promise<ApiResponse<Conversation>>;
   }
   ```

2. **Application Layer**:
   ```typescript
   // application/use-cases/chat/SaveConversationUseCase.ts
   export class SaveConversationUseCase {
     constructor(private chatService: IChatService) {}

     async execute(conversationId: string, title: string) {
       // Business logic here
       return this.chatService.saveConversation(conversationId, title);
     }
   }
   ```

3. **Infrastructure Layer**:
   ```typescript
   // infrastructure/api/ChatApiService.ts
   export class ChatApiService implements IChatService {
     async saveConversation(conversationId: string, title: string) {
       // HTTP call to FastAPI
     }
   }
   ```

4. **Presentation Layer**:
   ```typescript
   // presentation/hooks/useChat.ts
   export function useChat() {
     const saveConversation = async (conversationId: string, title: string) => {
       const useCase = new SaveConversationUseCase(chatService);
       return useCase.execute(conversationId, title);
     };

     return { saveConversation };
   }
   ```

## File Naming Conventions

- **Entities**: PascalCase (User.ts, Conversation.ts)
- **Interfaces**: PascalCase with "I" prefix (IAuthService.ts, IChatService.ts)
- **Use Cases**: PascalCase with "UseCase" suffix (LoginUseCase.ts, SendMessageUseCase.ts)
- **Components**: PascalCase (Button.tsx, ChatMessage.tsx)
- **Hooks**: camelCase with "use" prefix (useAuth.ts, useChat.ts)
- **Stores**: camelCase with "Store" suffix (authStore.ts, chatStore.ts)
- **Config**: camelCase (api.config.ts, constants.ts)

## Import Rules

- Domain layer: No imports from other layers
- Application layer: Can import from domain only
- Infrastructure layer: Can import from domain only
- Presentation layer: Can import from application, infrastructure, and domain
- Config layer: Can be imported by any layer

## Next Steps

1. Implement API clients (infrastructure/api/)
2. Implement use cases (application/use-cases/)
3. Build UI components (presentation/components/)
4. Connect everything in pages (app/)
