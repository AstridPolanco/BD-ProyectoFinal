from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from groq import Groq

from database import ejecutar_sql, get_schema
from security import validar_sql, limpiar_sql_de_ia

app = Flask(__name__, static_folder="static")
CORS(app)

#  CONFIG GROQ

GROQ_API_KEY = ""   # ← pega tu API key de Groq aquí
GROQ_MODEL   = "llama-3.3-70b-versatile" 
cliente_groq = Groq(api_key=GROQ_API_KEY)

#  SYSTEM PROMPT
SYSTEM_PROMPT = """Eres un experto en SQL Server. Tu unica funcion es convertir preguntas en espanol a consultas SQL SELECT validas para la base de datos DonaldV2.

REGLAS OBLIGATORIAS:
1. Responde UNICAMENTE con el codigo SQL, sin explicaciones, sin texto adicional, sin markdown, sin bloques de codigo.
2. Solo genera consultas SELECT. Nunca generes DROP, DELETE, UPDATE, INSERT, ALTER.
3. Usa exactamente los nombres de tablas y columnas que aparecen en el esquema.
4. Si la pregunta no se puede responder con los datos disponibles, responde: SELECT 'No tengo informacion suficiente para responder esa pregunta' AS Mensaje
5. Usa TOP 100 cuando la consulta pueda retornar muchos registros, para no saturar el sistema.
6. Las fechas en SQL Server se escriben como '2024-01-01'. Para año actual usa YEAR(GETDATE()).
7. Para filtrar rangos de tiempo relativos (ej. últimos 3 meses, mes pasado, hace un año), utiliza la función DATEDIFF de SQL Server. Ejemplo para el mes pasado: DATEDIFF(MONTH, Fecha, GETDATE()) = 1.
8. Para buscar texto usa LIKE '%texto%'.
9. Siempre usa alias descriptivos en espanol para las columnas del resultado.
10. Para nombres completos de personas concatena: PrimerNombre + ' ' + PrimerApellido.
11. SIEMPRE usa la tabla OrdeDeTrabajo (no OrdenDeTrabajo) y DetalleManoDeObra (no DetalleManoDObra).
12. En la tabla MovimientoMaterial usa 'Unidades' para cantidades y 'FechaMovimiento' para fechas. Nunca uses columnas inventadas como 'Cantidad' o 'Fecha'.

ESQUEMA DE LA BASE DE DATOS DonaldV2:

SOCIOS y PERSONAS
SocioNegocio: CodigoSocio(PK), PrimerNombre, SegundoNombre, PrimerApellido, SegundoApellido, FechaNacimiento, CUI, NIT, RazonSocial, Genero, CodigoTipoSocioNegocio
SocioNegocioDireccion: CodigoSocioNegocioDireccion(PK), Calle, Avenida, Otro, Zona, Colonia, CodigoMunicipio, DepartamentoCodigo, CodigoTipoDireccion, CodigoSocioNegocio(FK)
SocioNegocioTelefono: CodigoSocio(FK), CodigoSocioNegocioTelefono, Numero, CodigoTipoTelefono
TipoSocioNegocio: CodigoTipoSocioNegocio(PK), Descripcion

CLIENTES, EMPLEADOS, PROVEEDORES
Cliente: CodigoCliente(PK), CodigoSocio(FK -> SocioNegocio)
Empleado: CodigoEmpleado(PK), CodigoSocio(FK -> SocioNegocio)
Proveedor: CodigoProveedor(PK), CodigoSocio(FK -> SocioNegocio)

AUTOS
Automovil: CodigoAutomovil(PK), Placa, Color, VIN, Motor, Modelo(año), CodigoLinea(FK), CodigoMarca(FK)
Marca: CodigoMarca(PK), Descripcion
Linea: CodigoMarca(FK), CodigoLinea(PK), Descripcion

CITAS Y ORDENES
Cita: NumeroCita(PK), CodigoSucursal, CodigoCliente(FK), FechaCita, FechaRecepcion, Observaciones, CodigoEmpleado(FK), CodigoAutomovil(FK)
Diagnostico: NumeroDiagnostico(PK), NumeroCita(FK), CodigoDiagnostico(FK)
TipoDiagnostico: CodigoDiagnostico(PK), Descripcion
OrdeDeTrabajo: NumeroOrden(PK), FechaOrden, Estado, NumeroCita(FK -> Cita)
DetalleManoDeObra: NumeroOrden(FK), NumeroManoDeObra, Unidades, CodigoManoObra(FK), FechaInicio, FechaFin, CodigoEmpleado(FK), Serie, Numero, CodigoTipoDocumentoFiscal
DetalleMaterial: NumeroOrden(FK), NumeroManoDeObra, CodigoMaterial(FK), NumeroDetalleMaterial, Unidades, PrecioVenta
ManoObra: CodigoManoObra(PK), Descripcion, Precio

MATERIALES E INVENTARIO
Material: CodigoMaterial(PK), Descripcion, PrecioCosto, PrecioVenta, Saldo
Bodega: CodigoSucursal(FK), CodigoBodega(PK), Descripcion
MovimientoMaterial: NumeroMovimiento(PK), CodigoSucursal, CodigoBodega, FechaMovimiento, Referencia, CodigoTipoMovimiento
DetalleMovimientoMaterial: NumeroMovimiento(FK), CodigoMaterial(FK), LineaDetalleMovimiento, Unidades

FACTURACION Y PAGOS
DocumentoFiscal: CodigoTipoDocumentoFiscal(FK), Serie, Numero(PK), FechaEmision, NIT, ValorTotal, IVA, Estado
TipoDocumentoFiscal: CodigoTipoDocumentoFiscal(PK), Descripcion
DetallePago: Serie, Numero(FK -> DocumentoFiscal), CodigoTipoDocumentoFiscal, NumeroPago, Valor, CodigoTipoPago(FK)
TipoPago: CodigoTipoPago(PK), Descripcion

SUCURSALES Y TALLERES
Taller: CodigoTaller(PK), RazonSocial, NombreComercial, NIT
Sucursal: CodigoSucursal(PK), NombreSucursal, CodigoTaller(FK)
SucursalDireccion: CodigoSucursal(FK), CodigoSucursalDireccion, Calle, Avenida, Zona, CodigoMunicipio, DepartamentoCodigo
SucursalTelefono: CodigoSucursal(FK), CodigoSucursalTelefono, Numero, CodigoTipoTelefono

COMPRAS Y PROVEEDORES
Requisicion: NumeroRequision(PK), FechaRequisicion, CodigoSucursal, CodigoEmpleado
Cotizacion: NumeroRequision(FK), NumeroCotizacion(PK), FechaCotizacion, CodigoProveedore(FK)
DetalleCotizacion: NumeroRequision(FK), NumeroCotizacion(FK), LineaCotizacion, CodigoMaterial, Unidades, PrecioCompra
Pedido: NumeroRequision(FK), NumeroCotizacion(FK), NumeroPedido(PK)
DetallePedido: NumeroPedido(FK), LineaPedido, CodigoMaterial(FK), Unidades, UnidadesRecibidas, PrecioCompra

NOMINA Y RRHH
ContratroTrabajo: NumeroContrato(PK), FechaEmision, Estado, CodigoTaller, CodigoEmpleado(FK), CodigoDepartamentoTrabajo, CodigoPuestoTrabajo
Asistencia: CorellativoAsistencia(PK), CodigoEmpleado(FK), CodigoTipoAsistencia, FechaIngreso, FechaEgreso, Origen
Nomina: CodigoNomina(PK), CodigoSucursal, Descripcion, Inicio, Fin
NominaResumen: CodigoNomina(FK), NumeroResumen, CodigoEmpleado(FK), Salario, TotalIngresos, TotalDescuentos, Liquido, CodigoSucursal
DetalleNomina: CodigoNomina(FK), NumeroDetalleNomina, CodigoTipoMovimientoNomina, Valor, CodigoEmpleado, CodigoSucursal

GEOGRAFIA
Departamento: CodigoDepartamento(PK), Descripcion
Municipio: DepartamentoCodigo(FK), CodigoMunicipio(PK), Descripcion

RELACIONES IMPORTANTES:
- SocioNegocio es la tabla base de clientes, empleados y proveedores
- Cliente.CodigoSocio → SocioNegocio.CodigoSocio
- Empleado.CodigoSocio → SocioNegocio.CodigoSocio
- Proveedor.CodigoSocio → SocioNegocio.CodigoSocio
- Cita.CodigoCliente → Cliente.CodigoCliente
- Cita.CodigoAutomovil → Automovil.CodigoAutomovil
- OrdeDeTrabajo.NumeroCita → Cita.NumeroCita
- DetalleManoDeObra.NumeroOrden → OrdeDeTrabajo.NumeroOrden
- DetalleMaterial.NumeroOrden → OrdeDeTrabajo.NumeroOrden
- DocumentoFiscal con CodigoTipoDocumentoFiscal = 1 son FACTURAS
- DocumentoFiscal contiene facturas, notas de credito y debito
- DetallePago.Numero → DocumentoFiscal.Numero
- Automovil.CodigoMarca → Marca.CodigoMarca
- Automovil.CodigoLinea → Linea.CodigoLinea
- Municipio.DepartamentoCodigo → Departamento.CodigoDepartamento

EJEMPLOS DE CONSULTAS:
Pregunta: Cuantos clientes hay
SQL: SELECT COUNT(*) AS TotalClientes FROM Cliente

Pregunta: Muestra las 10 marcas de autos mas atendidas
SQL: SELECT TOP 10 m.Descripcion AS Marca, COUNT(c.NumeroCita) AS TotalCitas FROM Cita c JOIN Automovil a ON c.CodigoAutomovil = a.CodigoAutomovil JOIN Marca m ON a.CodigoMarca = m.CodigoMarca GROUP BY m.Descripcion ORDER BY TotalCitas DESC

Pregunta: Total de ventas del año 2024
SQL: SELECT SUM(ValorTotal) AS TotalVentas2024 FROM DocumentoFiscal WHERE YEAR(FechaEmision) = 2024 AND CodigoTipoDocumentoFiscal = 1

Pregunta: Muestra el telefono del cliente con NIT 1000200-6
SQL: SELECT sn.PrimerNombre + ' ' + sn.PrimerApellido AS NombreCliente, snt.Numero AS Telefono FROM Cliente c JOIN SocioNegocio sn ON c.CodigoSocio = sn.CodigoSocio JOIN SocioNegocioTelefono snt ON sn.CodigoSocio = snt.CodigoSocio WHERE sn.NIT LIKE '%1000200-6%'

Pregunta: Muestra los 5 empleados con mas ordenes
SQL: SELECT TOP 5 sn.PrimerNombre + ' ' + sn.PrimerApellido AS NombreEmpleado, COUNT(o.NumeroOrden) AS TotalOrdenes FROM Empleado e JOIN SocioNegocio sn ON e.CodigoSocio = sn.CodigoSocio JOIN Cita c ON c.CodigoEmpleado = e.CodigoEmpleado JOIN OrdeDeTrabajo o ON o.NumeroCita = c.NumeroCita GROUP BY sn.PrimerNombre, sn.PrimerApellido ORDER BY TotalOrdenes DESC

Pregunta: Historial de servicios del vehiculo con placa ABC-123
SQL: SELECT o.NumeroOrden, o.FechaOrden, mo.Descripcion AS Servicio, dmo.FechaInicio, dmo.FechaFin FROM OrdeDeTrabajo o JOIN Cita ci ON o.NumeroCita = ci.NumeroCita JOIN Automovil a ON ci.CodigoAutomovil = a.CodigoAutomovil JOIN DetalleManoDeObra dmo ON o.NumeroOrden = dmo.NumeroOrden JOIN ManoObra mo ON dmo.CodigoManoObra = mo.CodigoManoObra WHERE a.Placa LIKE '%ABC-123%'

Pregunta: Total de ventas por mes en 2023
SQL: SELECT MONTH(FechaEmision) AS Mes, SUM(ValorTotal) AS TotalVentas FROM DocumentoFiscal WHERE YEAR(FechaEmision) = 2023 AND CodigoTipoDocumentoFiscal = 1 GROUP BY MONTH(FechaEmision) ORDER BY Mes

Pregunta: Cuantas citas hubo en 2024
SQL: SELECT COUNT(*) AS TotalCitas FROM Cita WHERE YEAR(FechaCita) = 2024

Pregunta: Muestra los proveedores con mas cotizaciones
SQL: SELECT TOP 10 sn.RazonSocial AS Proveedor, COUNT(co.NumeroCotizacion) AS TotalCotizaciones FROM Proveedor p JOIN SocioNegocio sn ON p.CodigoSocio = sn.CodigoSocio JOIN Cotizacion co ON p.CodigoProveedor = co.CodigoProveedore GROUP BY sn.RazonSocial ORDER BY TotalCotizaciones DESC

Pregunta: Total de la nomina de enero 2024
SQL: SELECT SUM(nr.TotalIngresos) AS TotalIngresos, SUM(nr.TotalDescuentos) AS TotalDescuentos, SUM(nr.Liquido) AS TotalLiquido FROM Nomina n JOIN NominaResumen nr ON n.CodigoNomina = nr.CodigoNomina WHERE MONTH(n.Inicio) = 1 AND YEAR(n.Inicio) = 2024

Pregunta: Clientes que tienen 30 años
SQL: SELECT sn.PrimerNombre + ' ' + sn.PrimerApellido AS NombreCliente FROM Cliente c JOIN SocioNegocio sn ON c.CodigoSocio = sn.CodigoSocio WHERE DATEDIFF(YEAR, sn.FechaNacimiento, GETDATE()) = 30

Pregunta: Muestra las placas de los autos junto con el nombre de su dueño
SQL: SELECT TOP 100 a.Placa, sn.PrimerNombre + ' ' + sn.PrimerApellido AS NombrePropietario FROM Automovil a JOIN Cita c ON a.CodigoAutomovil = c.CodigoAutomovil JOIN Cliente cl ON c.CodigoCliente = cl.CodigoCliente JOIN SocioNegocio sn ON cl.CodigoSocio = sn.CodigoSocio GROUP BY a.Placa, sn.PrimerNombre, sn.PrimerApellido

Pregunta: Muestra los movimientos de materiales
SQL: SELECT TOP 100 mm.NumeroMovimiento, mm.FechaMovimiento, mm.Unidades, mm.Referencia, m.Descripcion AS Material FROM MovimientoMaterial mm JOIN DetalleMovimientoMaterial dmm ON mm.NumeroMovimiento = dmm.NumeroMovimiento JOIN Material m ON dmm.CodigoMaterial = m.CodigoMaterial

Pregunta: Listar las primeras 20 citas indicando la fecha el nombre y apellido del empleado asignado
SQL: SELECT TOP 20 c.FechaCita, sn.PrimerNombre + ' ' + sn.PrimerApellido AS NombreEmpleado FROM Cita c JOIN Empleado e ON c.CodigoEmpleado = e.CodigoEmpleado JOIN SocioNegocio sn ON e.CodigoSocio = sn.CodigoSocio ORDER BY c.FechaCita

Pregunta: Cuantos empleados hay registrados en cada departamento de trabajo
SQL: SELECT dt.Descripcion AS Departamento, COUNT(ct.CodigoEmpleado) AS TotalEmpleados FROM DepartamentoTrabajo dt JOIN ContratroTrabajo ct ON dt.CodigoDepartamentoTrabajo = ct.CodigoDepartamentoTrabajo GROUP BY dt.Descripcion ORDER BY TotalEmpleados DESC

Pregunta: Muestra un resumen de los primeros 10 detalles de mano de obra registrados
SQL: SELECT TOP 10 dmo.NumeroOrden, dmo.NumeroManoDeObra, mo.Descripcion AS Servicio, dmo.Unidades, dmo.FechaInicio, dmo.FechaFin FROM DetalleManoDeObra dmo JOIN ManoObra mo ON dmo.CodigoManoObra = mo.CodigoManoObra"""


def preguntar_ia(pregunta: str, schema: str) -> str:
    """
    Envia la pregunta a Groq con el system prompt y retorna el SQL generado.
    Groq es extremadamente rapido — responde en menos de 2 segundos.
    """
    respuesta = cliente_groq.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": f"PREGUNTA: {pregunta}\nSQL:"
            }
        ],
        temperature=0.1,
        max_tokens=500,
    )
    return respuesta.choices[0].message.content.strip()


# ─────────────────────────────────────────────
#  CACHE DEL SCHEMA
# ─────────────────────────────────────────────
_schema_cache = None

def obtener_schema():
    global _schema_cache
    if _schema_cache is None:
        print("Cargando schema de DonaldV2...")
        _schema_cache = get_schema()
        print(f"Schema cargado: {len(_schema_cache)} caracteres")
    return _schema_cache


# ═══════════════════════════════════════════
#  ENDPOINTS
# ═══════════════════════════════════════════

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/test")
def test():
    """Verifica que Flask, Groq y SQL Server funcionen."""
    resultado = {
        "flask":      "OK",
        "sql_server": "ERROR",
        "groq":       "ERROR",
        "modelo":     GROQ_MODEL,
    }

    # Test SQL Server
    try:
        rows = ejecutar_sql("SELECT COUNT(*) AS Total FROM SocioNegocio")
        resultado["sql_server"] = f"OK — {rows[0]['Total']:,} socios en BD"
    except Exception as e:
        resultado["sql_server"] = f"ERROR: {str(e)}"

    # Test Groq
    try:
        resp = cliente_groq.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": "Responde solo: OK"}],
            max_tokens=10,
        )
        resultado["groq"] = f"OK — Groq responde: {resp.choices[0].message.content.strip()}"
    except Exception as e:
        resultado["groq"] = f"ERROR: {str(e)}"

    return jsonify(resultado)


@app.route("/api/schema")
def schema():
    try:
        s = obtener_schema()
        return jsonify({"success": True, "schema": s})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/consulta", methods=["POST"])
def consulta():
    """
    Recibe: { "pregunta": "cuantos clientes hay?" }
    Devuelve: { "success": true, "sql": "SELECT...", "datos": [...], "total": N }
    """
    body = request.get_json()
    if not body or "pregunta" not in body:
        return jsonify({"success": False, "error": "Falta el campo 'pregunta'"}), 400

    pregunta = body["pregunta"].strip()
    if not pregunta:
        return jsonify({"success": False, "error": "La pregunta esta vacia"}), 400

    print(f"\n{'='*50}")
    print(f"PREGUNTA: {pregunta}")

    try:
        schema_txt = obtener_schema()

        print("Consultando Groq...")
        respuesta_ia = preguntar_ia(pregunta, schema_txt)
        print(f"RESPUESTA IA RAW: {respuesta_ia[:200]}...")

        sql_extraido = limpiar_sql_de_ia(respuesta_ia)
        print(f"SQL EXTRAIDO: {sql_extraido}")

        es_valido, resultado_validacion = validar_sql(sql_extraido)
        if not es_valido:
            print(f"SQL BLOQUEADO: {resultado_validacion}")
            return jsonify({
                "success": False,
                "error":   resultado_validacion,
                "sql":     sql_extraido
            }), 400

        sql_final = resultado_validacion
        print(f"SQL FINAL: {sql_final}")

        datos = ejecutar_sql(sql_final)
        print(f"RESULTADO: {len(datos)} filas")

        return jsonify({
            "success":  True,
            "pregunta": pregunta,
            "sql":      sql_final,
            "datos":    datos,
            "total":    len(datos)
        })

    except Exception as e:
        print(f"ERROR: {str(e)}")
        return jsonify({
            "success": False,
            "error":   str(e)
        }), 500


# ─────────────────────────────────────────────
#  INICIAR SERVIDOR
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*50)
    print("  DONALD GPT — Backend con Groq")
    print("="*50)
    print(f"  Modelo IA:     {GROQ_MODEL}")
    print(f"  Proveedor:     Groq (100% gratuito)")
    print(f"  Base de datos: DonaldV2 (localhost)")
    print("="*50)
    print("  Interfaz web:  http://localhost:5000")
    print("  Test API:      http://localhost:5000/api/test")
    print("="*50 + "\n")

    try:
        obtener_schema()
    except Exception as e:
        print(f"ADVERTENCIA: No se pudo cargar el schema: {e}")
        print("Verifica que SQL Server este corriendo y DonaldV2 exista.\n")

    app.run(debug=True, port=5000)