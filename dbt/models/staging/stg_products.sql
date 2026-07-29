select
    cast(product_id as {{ dbt.type_int() }}) as product_id,
    cast(product_name as {{ dbt.type_string() }}) as product_name,
    cast(aisle_id as {{ dbt.type_int() }}) as aisle_id,
    cast(department_id as {{ dbt.type_int() }}) as department_id
from {{ source('raw', 'products') }}
