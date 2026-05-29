import pyodbc
 
CONN_STRING = (
    "Driver={ODBC Driver 18 for SQL Server};"
    "Server=localhost\\SQLEXPRESS;"
    "Database=DonaldV2;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)
 
def get_connection():
    """Retorna una conexion activa a SQL Server."""
    return pyodbc.connect(CONN_STRING)
 
def ejecutar_sql(sql: str):
    """
    Ejecuta un SELECT en DonaldV2 y retorna los resultados como lista de dicts.
    Lanza excepcion si falla.
    """
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql)
    cols = [col[0] for col in cursor.description]
    rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
    conn.close()
    return rows
 
def get_schema():
    """
    Retorna un resumen del esquema de DonaldV2:
    nombre de tabla + sus columnas con tipo de dato.
    Se usa para incluirlo en el prompt de la IA.
    """
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            t.TABLE_NAME,
            c.COLUMN_NAME,
            c.DATA_TYPE,
            c.IS_NULLABLE
        FROM INFORMATION_SCHEMA.TABLES t
        JOIN INFORMATION_SCHEMA.COLUMNS c 
            ON t.TABLE_NAME = c.TABLE_NAME
        WHERE t.TABLE_TYPE = 'BASE TABLE'
            AND t.TABLE_NAME NOT IN ('sysdiagrams', 'EjemploTransaccion')
        ORDER BY t.TABLE_NAME, c.ORDINAL_POSITION
    """)
    
    tablas = {}
    for row in cursor.fetchall():
        tabla, col, tipo, nullable = row
        if tabla not in tablas:
            tablas[tabla] = []
        tablas[tabla].append(f"{col} ({tipo}{'?' if nullable == 'YES' else ''})")
    
    conn.close()
    
    # Convertir a texto legible para la IA
    schema_text = ""
    for tabla, cols in tablas.items():
        schema_text += f"Tabla: {tabla}\n"
        schema_text += "  Columnas: " + ", ".join(cols) + "\n\n"
    
    return schema_text