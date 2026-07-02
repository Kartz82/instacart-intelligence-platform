
    
    

select
    aisle_id as unique_field,
    count(*) as n_records

from "instacart_db"."raw"."aisles"
where aisle_id is not null
group by aisle_id
having count(*) > 1


