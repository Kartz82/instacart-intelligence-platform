select
    cast(department_id as {{ dbt.type_int() }}) as department_id,
    cast(department as {{ dbt.type_string() }}) as department_name
from {{ source('raw', 'departments') }}
