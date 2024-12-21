class QueryBuilder:
    """
    Constructs an SQL query with optional WHERE conditions.

    This function takes a base SQL query and any number of optional keyword
    arguments representing WHERE conditions. It appends these conditions to
    the base query, using the format "key = %s". If a condition value is None,
    it is skipped.

    Args:
        base_query (str): The base SQL query to which conditions will be appended.
        **where_conditions: Arbitrary keyword arguments representing WHERE conditions.
                            Each key is the column name, and each value is the value to filter by.

    Returns:
        tuple: A tuple containing the constructed query (str) and a list of arguments (list).
               The query is ready to be executed with a database cursor's execute method,
               using the arguments list for parameter substitution.

    Example:
        >>> base_query = "SELECT * FROM INFORMATION_SCHEMA.PLUGINS"
        >>> query, args = build(base_query, name="mysqlx")
        >>> print(query)
        SELECT * FROM INFORMATION_SCHEMA.PLUGINS WHERE name = %s
        >>> print(args)
        ['mysqlx']
    """

    @staticmethod
    def build(base_query, **where_conditions):
        conditions = []
        args = []
        for key, value in where_conditions.items():
            if value is None:
                continue
            conditions.append(f"{key} = %s")
            args.append(value)
        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)
        return base_query, args
