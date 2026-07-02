select
    department_id::integer as department_id,
    department::varchar as department_name
from {{ source('raw', 'departments') }}
