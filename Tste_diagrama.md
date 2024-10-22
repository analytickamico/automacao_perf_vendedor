```mermaid

graph TB;
    A[Usuário] -->|Acessa| B[Google Sites]
    B -->|Incorpora| C[Metabase Dashboard]
    C -->|Redireciona| D[Traefik Proxy]
    D -->|HTTPS| E[Container Docker Metabase]
    E -->|Metadata| F[Container Docker PostgreSQL]
    E -->|Consulta| G[AWS Athena]
    G -->|Acessa| H[Data Lake]
    
    subgraph AWS EC2
        C
        D
        E
        F
    end
    
    subgraph AWS
        G
        subgraph "Data Lake"
            H -->|Bronze| I[Dados Brutos]
            H -->|Prata| J[Dados Processados]
            H -->|Ouro| K[Dados Agregados]
        end
    end

    classDef aws fill:#FF9900,stroke:#232F3E,stroke-width:2px;
    classDef container fill:#1488C6,stroke:#0B5394,stroke-width:2px;
    classDef default fill:#f9f9f9,stroke:#333,stroke-width:1px;

    class G,H,I,J,K aws;
    class D,E,F container;

    ```