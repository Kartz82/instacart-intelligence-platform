select
    aisle_id::integer as aisle_id,
    aisle::varchar as aisle_name
from {{ source('raw', 'aisles') }}
