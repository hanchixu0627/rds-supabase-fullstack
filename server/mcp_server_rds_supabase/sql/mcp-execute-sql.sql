-- Supabase MCP execute_sql: RPC function definition.

BEGIN;

CREATE OR REPLACE FUNCTION public.execute_sql(query text, read_only boolean DEFAULT false)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'extensions', 'public'
AS $function$
DECLARE
    _rows   jsonb := '[]'::jsonb;
    _rec    record;
    _n      bigint;
    _claims text;
    _first  text;
BEGIN
    -- service_role only
    _claims := nullif(current_setting('request.jwt.claims', true), '');

    IF _claims IS NOT NULL
       AND coalesce(_claims::jsonb ->> 'role', '') <> 'service_role' THEN
        RAISE EXCEPTION 'execute_sql: access denied, service_role only'
            USING ERRCODE = '42501';
    END IF;

    -- read_only gate
    IF read_only THEN
        IF query !~* '^\s*(--[^\n]*\n\s*)*(select|with|values|table|explain)\y' THEN
            RAISE EXCEPTION 'execute_sql: read_only mode allows only SELECT / WITH / VALUES / TABLE / EXPLAIN'
                USING ERRCODE = '42501';
        END IF;
        IF query ~* '^\s*(--[^\n]*\n\s*)*with\y'
           AND query ~* '\y(insert|update|delete|merge)\y' THEN
            RAISE EXCEPTION 'execute_sql: read_only mode does not allow data-modifying statements inside WITH'
                USING ERRCODE = '42501';
        END IF;
        IF query ~* '^\s*(--[^\n]*\n\s*)*explain\y'
           AND query ~* '\yanalyze\y' THEN
            RAISE EXCEPTION 'execute_sql: read_only mode does not allow EXPLAIN ANALYZE'
                USING ERRCODE = '42501';
        END IF;
    END IF;

    -- first keyword, case-insensitive
    _first := lower((regexp_match(query, '^\s*(?:--[^\n]*\n\s*)*([a-z_]+)', 'i'))[1]);

    IF _first IN ('select', 'with', 'values', 'table', 'explain',
                  'insert', 'update', 'delete', 'merge') THEN
        BEGIN
            FOR _rec IN EXECUTE query LOOP
                _rows := _rows || to_jsonb(_rec);
            END LOOP;
            RETURN _rows;
        EXCEPTION
            -- fall through to direct execution
            WHEN invalid_cursor_definition THEN NULL;
            -- genuine syntax errors propagate
            WHEN syntax_error THEN
                RAISE;
        END;

        IF read_only THEN
            RAISE EXCEPTION 'execute_sql: read_only mode supports only row-returning queries'
                USING ERRCODE = '42501';
        END IF;
    END IF;

    EXECUTE query;
    GET DIAGNOSTICS _n = ROW_COUNT;
    RETURN jsonb_build_array(
        jsonb_build_object('success', true, 'rows_affected', _n)
    );
END;
$function$;

COMMENT ON FUNCTION public.execute_sql(text, boolean) IS
    'RPC function definition for the Supabase MCP execute_sql tool.';

REVOKE ALL ON FUNCTION public.execute_sql(text, boolean) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.execute_sql(text, boolean) FROM anon;
REVOKE ALL ON FUNCTION public.execute_sql(text, boolean) FROM authenticated;
GRANT EXECUTE ON FUNCTION public.execute_sql(text, boolean) TO service_role;

COMMIT;

-- refresh PostgREST schema cache
NOTIFY pgrst, 'reload schema';
