
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

select
    aisle_id as unique_field,
    count(*) as n_records

from "instacart_db"."raw"."aisles"
where aisle_id is not null
group by aisle_id
having count(*) > 1



  
  
      
    ) dbt_internal_test