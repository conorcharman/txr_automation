"""
Source Query
============

Stores the canonical SQL used to extract the daily reconciliation report
from the external SQL Server (which hosts the FIGARO_CL linked server),
plus a helper to assemble the ODBC connection string from individual
environment variables.
"""

import os

#: Environment variable names for individual ODBC connection components.
DAILY_RECON_SERVER_ENV = "DAILY_RECON_SERVER"
DAILY_RECON_DATABASE_ENV = "DAILY_RECON_DATABASE"
DAILY_RECON_UID_ENV = "DAILY_RECON_UID"
DAILY_RECON_PWD_ENV = "DAILY_RECON_PWD"
DAILY_RECON_DRIVER_ENV = "DAILY_RECON_DRIVER"
DAILY_RECON_TRUST_CERT_ENV = "DAILY_RECON_TRUST_CERT"

#: Canonical daily reconciliation extraction query (runs server-side via
#: the FIGARO_CL linked server using OPENQUERY).
DAILY_RECON_QUERY = r"""
SELECT *
FROM openquery(FIGARO_CL, '

    SELECT
    -- 1 Report status
    T3.REPSTS,

    -- 2 Transaction Reference Number
    T1.TRADEREF,

    -- 3-6 Core identifiers
    T3.VENUETXNID,
    T3.EXENTITYID,
    T3.FRMDIRIND,
    T3.SUBMITID,

    -- 7 Buyer ID (T4 or T5)
    COALESCE(T4.INDIDCODE, T5.ENTIDCODE) AS BUYER_ID,

    -- 8 Buyer branch country
    COALESCE(T4.BRCHCNT, T5.BRCHCNT) AS BUYER_BRANCH_COUNTRY,

    -- 9-11 Buyer personal details
    T4.PTYFORE   AS BUYER_FIRST_NAME,
    T4.PTYSURN   AS BUYER_SURNAME,
    T4.PTYDOB    AS BUYER_DOB,

    -- 12 Buyer decision maker
    COALESCE(T3.BUYDECIND, T3.BUYDECENT) AS BUY_DECISION_MAKER,

    -- 13-15 Buyer decision details
    T3.BUYDECFORE,
    T3.BUYDECFORE AS BUYDEC_SURNAME,
    T3.BUYDECDOB,

    -- 16 Seller ID (same logic as buyer)
    COALESCE(T4.INDIDCODE, T5.ENTIDCODE) AS SELLER_ID,

    -- 17 Seller branch country
    COALESCE(T4.BRCHCNT, T5.BRCHCNT) AS SELLER_BRANCH_COUNTRY,

    -- 18-20 Seller personal details
    T4.PTYFORE   AS SELLER_FIRST_NAME,
    T4.PTYSURN   AS SELLER_SURNAME,
    T4.PTYDOB    AS SELLER_DOB,

    -- 21 Seller decision maker
    COALESCE(T3.BUYDECIND, T3.BUYDECENT) AS SELL_DECISION_MAKER,

    -- 22-24 Seller decision details
    T3.BUYDECFORE AS SELLDEC_FIRST_NAME,
    T3.BUYDECFORE AS SELLDEC_SURNAME,
    T3.BUYDECDOB AS SELLDEC_DOB,

    -- 25-37 Trade details
    T3.TRANSIND,
    T3.TRANSIDBUY,
    T3.TRANSIDSEL,
    T3.TRDDATTIM,
    T3.TRADING_CAPACITY,
    T3.QUANTITY,
    T3.QUANCUR,
    T3.DERIVATIVE_NOTIONAL_INCREASE_DECREASE,
    T3.PRICE,
    T3.PRICUR,
    T3.NETAMT,
    T3.VENUE,
    T3.CNTBRCHMEM,

    -- 57-60 Firm / execution
    T3.INVDECFIRM,
    T3.CNTBRCHDEC,
    T3.EXINFIRM,
    T3.CNTBRCHEX,

    -- 62-65 flags
    T3.SHRTSELIND,
    T3.OTCPSTIND,
    T3.COMDERIND,
    T3.SECFININD

FROM AJBCOPY.CLDATA.TXNREP T1
JOIN AJBCOPY.CLDATA.TXNRPTRD T2
    ON T2.TRADE_REFERENCE = T1.Report_Reference
JOIN AJBCOPY.CLDATA.TXNREPESMA T3
    ON T3.REPORT_REFERENCE = T1.REPORT_REFERENCE
JOIN AJBCOPY.CLDATA.ESMAPTYIND T4
    ON T4.REPORT_REFERENCE = T1.REPORT_REFERENCE
JOIN AJBCOPY.CLDATA.ESMAPTYENT T5
    ON T5.REPORT_REFERENCE = T1.REPORT_REFERENCE
WHERE
    T1.TRANSACTION_REPORT_STATUS = ''WAIT''
    AND T2.REPORTABLE = ''Y''
    AND T3.TRADING_DATE_TIME >= CURRENT DATE - 2 MONTHS
    AND T3.TRADING_DATE_TIME < CURRENT DATE + 1 DAY
');
""".strip()


def get_source_odbc_connection_string() -> str:
    """Assemble ODBC connection string from individual environment variables.

    Returns:
        The assembled ODBC connection string.

    Raises:
        RuntimeError: If required variables are not set.

    Example:
        Environment variables:
            DAILY_RECON_SERVER=10.62.136.8,1433
            DAILY_RECON_DATABASE=FIGARO
            DAILY_RECON_UID=app_user
            DAILY_RECON_PWD=secret123
            DAILY_RECON_DRIVER=ODBC Driver 17 for SQL Server  (optional, default used)
            DAILY_RECON_TRUST_CERT=yes  (optional, default used)

        Returns:
            DRIVER={ODBC Driver 17 for SQL Server};SERVER=10.62.136.8,1433;
            DATABASE=FIGARO;UID=app_user;PWD=secret123;TrustServerCertificate=yes
    """
    # Required components
    server = os.environ.get(DAILY_RECON_SERVER_ENV)
    database = os.environ.get(DAILY_RECON_DATABASE_ENV)
    uid = os.environ.get(DAILY_RECON_UID_ENV)
    pwd = os.environ.get(DAILY_RECON_PWD_ENV)

    # Optional components with defaults
    driver = os.environ.get(
        DAILY_RECON_DRIVER_ENV,
        "ODBC Driver 17 for SQL Server"
    )
    trust_cert = os.environ.get(DAILY_RECON_TRUST_CERT_ENV, "yes")

    # Validate required fields
    missing = []
    if not server:
        missing.append(DAILY_RECON_SERVER_ENV)
    if not database:
        missing.append(DAILY_RECON_DATABASE_ENV)
    if not uid:
        missing.append(DAILY_RECON_UID_ENV)
    if not pwd:
        missing.append(DAILY_RECON_PWD_ENV)

    if missing:
        msg = (
            f"Missing required SQL Server connection environment variables: "
            f"{', '.join(missing)}. "
            f"Add them to your .env file.\n\n"
            f"Example:\n"
            f"  {DAILY_RECON_SERVER_ENV}=10.62.136.8,1433\n"
            f"  {DAILY_RECON_DATABASE_ENV}=FIGARO\n"
            f"  {DAILY_RECON_UID_ENV}=app_user\n"
            f"  {DAILY_RECON_PWD_ENV}=secret123\n"
            f"  {DAILY_RECON_DRIVER_ENV}=ODBC Driver 17 for SQL Server (optional)\n"
            f"  {DAILY_RECON_TRUST_CERT_ENV}=yes (optional)"
        )
        raise RuntimeError(msg)

    # Assemble ODBC connection string
    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={uid};"
        f"PWD={pwd};"
        f"TrustServerCertificate={trust_cert}"
    )

    return conn_str



