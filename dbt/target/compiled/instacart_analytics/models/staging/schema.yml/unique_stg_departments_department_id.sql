
    
    

select
    department_id as unique_field,
    count(*) as n_records

from "instacart_db"."analytics_staging"."stg_departments"
where department_id is not null
group by department_id
having count(*) > 1


