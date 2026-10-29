import sqlglot
from sqlglot import exp


class UnsafeQueryError(ValueError):
    pass


def validate_and_limit_sql(sql: str, max_rows: int) -> str:
    candidate = sql.strip().removeprefix("```sql").removesuffix("```").strip()
    if not candidate:
        raise UnsafeQueryError("The model returned an empty query.")
    try:
        statements = sqlglot.parse(candidate, read="mysql")
    except sqlglot.errors.ParseError as exc:
        raise UnsafeQueryError("The generated SQL could not be parsed as MySQL.") from exc
    if len(statements) != 1 or statements[0] is None:
        raise UnsafeQueryError("Only one SQL statement is allowed.")

    query = statements[0]
    if not isinstance(query, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise UnsafeQueryError("Only read-only SELECT queries are allowed.")
    if query.find(exp.Into):
        raise UnsafeQueryError("SELECT INTO is not allowed.")

    existing_limit = query.args.get("limit")
    if existing_limit is None:
        query = query.limit(max_rows)
    else:
        try:
            requested = int(existing_limit.expression.this)
        except (AttributeError, TypeError, ValueError):
            raise UnsafeQueryError("The LIMIT must be a fixed integer.") from None
        if requested <= 0:
            raise UnsafeQueryError("The LIMIT must be greater than zero.")
        if requested > max_rows:
            query.set("limit", exp.Limit(expression=exp.Literal.number(max_rows)))
    return query.sql(dialect="mysql")
