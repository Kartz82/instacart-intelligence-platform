-- mart_customer_segments must classify every customer into exactly one of the four
-- segments the model defines, with no customer left unsegmented and no segment silently
-- empty.
--
-- An empty segment is the failure this test exists to catch: a CASE branch whose
-- condition can never be satisfied looks correct in review but produces a category that
-- never appears in the BI layer. That is how the removed "Early Lifecycle" branch
-- survived - its `total_orders <= 3` condition was unsatisfiable, because every user in
-- this extract has at least 4 orders.
--
-- Returns rows (i.e. fails) if any expected segment is missing or any customer is
-- unclassified.

with expected_segments as (
    select 'High Engagement' as behavioral_segment
    union all select 'Loyal Routine'
    union all select 'At Risk'
    union all select 'Moderate Engagement'
),

actual_segments as (
    select
        behavioral_segment,
        count(*) as customers
    from {{ ref('mart_customer_segments') }}
    group by behavioral_segment
),

missing_or_empty as (
    select
        expected_segments.behavioral_segment,
        'segment is missing or empty' as failure_reason
    from expected_segments
    left join actual_segments
        on expected_segments.behavioral_segment = actual_segments.behavioral_segment
    where coalesce(actual_segments.customers, 0) = 0
),

unexpected as (
    select
        actual_segments.behavioral_segment,
        'segment is not in the expected set' as failure_reason
    from actual_segments
    left join expected_segments
        on actual_segments.behavioral_segment = expected_segments.behavioral_segment
    where expected_segments.behavioral_segment is null
),

unclassified as (
    select
        coalesce(behavioral_segment, '<null>') as behavioral_segment,
        'customer has no segment' as failure_reason
    from {{ ref('mart_customer_segments') }}
    where behavioral_segment is null
)

select * from missing_or_empty
union all
select * from unexpected
union all
select * from unclassified
