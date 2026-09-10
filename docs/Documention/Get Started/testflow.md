Here is a simple **Mermaid flowchart** example you can use in a Markdown document:

```mermaid
flowchart TD
    A[Start] --> B[User submits request]
    B --> C{Is request valid?}

    C -->|Yes| D[Process request]
    C -->|No| E[Return validation error]

    E --> B
    D --> F{Approval required?}

    F -->|Yes| G[Send for approval]
    F -->|No| H[Complete request]

    G --> I{Approved?}
    I -->|Yes| H
    I -->|No| J[Reject request]

    H --> K[Notify user]
    J --> K
    K --> L[End]
```

### Example: Business process

```mermaid
flowchart LR
    A[Draft] --> B[Submit]
    B --> C[Manager Review]

    C -->|Approve| D[Approved]
    C -->|Reject| E[Rejected]
    C -->|Request Changes| A

    D --> F[Execute Action]
    F --> G[Complete]
```

### Example: System architecture flow

```mermaid
flowchart TD
    User[User] --> UI[Web Application]

    UI --> API[Django API]
    API --> DB[(Database)]

    API --> Files[Markdown Files]
    API --> GitHub[GitHub Repository]

    GitHub -->|Sync| Files

    API --> Auth[Authentication]
    Auth --> User
```

For your **Docs web app**, a useful flow would be:

```mermaid
flowchart TD
    A[Docs Application] --> B[Scan Documentation Folder]

    B --> C[Read Markdown Files]
    C --> D[Parse Front Matter]
    C --> E[Parse Markdown Content]

    D --> F[Build Documentation Tree]
    E --> F

    F --> G[Render Documentation UI]

    G --> H[Sidebar Navigation]
    G --> I[Markdown Content]
    G --> J[Search]

    K[GitHub Repository] --> L[Git Sync]
    L --> B
```
