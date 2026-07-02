select
    product_id::integer as product_id,
    product_name::varchar as product_name,
    aisle_id::integer as aisle_id,
    department_id::integer as department_id
from {{ source('raw', 'products') }}
