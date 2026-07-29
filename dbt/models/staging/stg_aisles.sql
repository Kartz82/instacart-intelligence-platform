select
    cast(aisle_id as {{ dbt.type_int() }}) as aisle_id,
    cast(aisle as {{ dbt.type_string() }}) as aisle_name
from {{ source('raw', 'aisles') }}
