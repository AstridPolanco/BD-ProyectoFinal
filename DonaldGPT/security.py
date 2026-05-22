import re
 
# Palabras prohibidas — cualquier consulta que las contenga es rechazada
PALABRAS_PROHIBIDAS = [
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE",
    "TRUNCATE", "EXEC", "EXECUTE", "SP_", "XP_", "GRANT",
    "REVOKE", "MERGE", "REPLACE", "CALL", "LOAD", "--", ";--",
    "/*", "*/", "WAITFOR", "SHUTDOWN", "BULK", "OPENROWSET",
    "OPENDATASOURCE", "DBCC"
]
 
def validar_sql(sql: str) -> tuple[bool, str]:
    """
    Valida que el SQL sea seguro (solo SELECT).
    
    Retorna:
        (True, sql_limpio)   si es valido
        (False, mensaje)     si es peligroso
    """
    if not sql or not sql.strip():
        return False, "La consulta SQL esta vacia."
    
    sql_upper = sql.upper().strip()
    
    # Debe empezar con SELECT
    if not sql_upper.startswith("SELECT"):
        return False, "Solo se permiten consultas SELECT. La IA genero una consulta no permitida."
    
    # Verificar palabras prohibidas
    for palabra in PALABRAS_PROHIBIDAS:
        # Buscar la palabra como token completo (no dentro de otra palabra)
        patron = r'\b' + re.escape(palabra) + r'\b'
        if re.search(patron, sql_upper):
            return False, f"Consulta bloqueada por seguridad: contiene '{palabra}'."
    
    # Verificar que no haya multiples statements (punto y coma)
    if ";" in sql:
        # Permitir solo si el punto y coma esta al final
        sql_sin_espacio = sql.strip()
        if sql_sin_espacio.count(";") > 1 or (
            ";" in sql_sin_espacio and not sql_sin_espacio.endswith(";")
        ):
            return False, "No se permiten multiples consultas en una sola peticion."
    
    # Limpiar espacios extras
    sql_limpio = sql.strip().rstrip(";")
    
    return True, sql_limpio
 
 
def limpiar_sql_de_ia(respuesta_ia: str) -> str:
    """
    Extrae el SQL puro de la respuesta de la IA.
    La IA a veces devuelve el SQL entre ```sql ... ``` o con texto extra.
    """
    respuesta = respuesta_ia.strip()
    
    # Remover bloques de codigo markdown ```sql ... ```
    if "```sql" in respuesta.lower():
        match = re.search(r'```sql\s*(.*?)\s*```', respuesta, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # Remover bloques ``` ... ``` sin especificar lenguaje
    if "```" in respuesta:
        match = re.search(r'```\s*(.*?)\s*```', respuesta, re.DOTALL)
        if match:
            return match.group(1).strip()
    
    # Buscar desde SELECT hasta el final
    match = re.search(r'(SELECT\s+.*)', respuesta, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    return respuesta