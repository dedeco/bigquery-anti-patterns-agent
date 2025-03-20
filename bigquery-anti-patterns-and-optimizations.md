drive.web-frontend_20250316.14_p1
bigquery
## BigQuery Anti-Patterns and Optimizations

Here are the anti-patterns described in the document, along with the original code, optimized code, and reasoning for each:

**1. Optimization: Necessary columns only** [cite: 69, 70, 71, 72]

* **Original Code:**

    ```sql
    select
    *
    from
    dataset.table`
    ```
* **Optimized Code:**

    ```sql
    select
    * EXCEPT (dim1, dim2)
    from
    `dataset.table`
    ```
* **Reasoning:**

    * Only select the columns necessary, especially in inner queries. [cite: 69]
    * `SELECT *` is cost inefficient and may also hurt performance. [cite: 70]
    * If the number of columns to return is large, consider using `SELECT * EXCEPT` to exclude unneeded columns. [cite: 71]
    * In some use cases, `SELECT * EXCEPT` may be necessary. [cite: 72]

**2. Optimization: Multiple WITH-clause References** [cite: 73, 74, 75, 76, 77, 78]

* **Original Code:**

    ```sql
    with a as (
    select
    ),
    b as (
    select
    ),
    c as (
    )
    select
    from a
    from a
    b.dim1, c.dim2
    from
    b, c;
    ```
* **Optimized Code:**

    ```sql
    create temp table a as
    select...;
    with b as (
    select
    from a
    ),
    c as (
    select
    from a
    )
    select
    b.dim1, c.dim2
    from
    b, c;
    ```
* **Reasoning:**

    * The `WITH` statement in BigQuery is like a Macro. [cite: 74, 75]
    * At runtime the contents of the subquery will be inlined every place the alias is referenced. [cite: 75, 76]
    * This can lead to query plan explosion as seen by the plan executing the same query stages multiple times. [cite: 76, 77]
    * Refactor to remove multiple references if possible or refactor to use `TEMP` table if the query cannot be refactored and duplicate stages are expensive. [cite: 77]

**3. Optimization: Subquery in filter with aggregation** [cite: 79, 80]

* **Original Code:**

    ```sql
    select
    t.dim1,
    t.dim2,
    t.metric1
    from
    `dataset.table
    t
    where t1.id not in (select
    id from dataset.table2`)
    ```
* **Optimized Code:**

    ```sql
    select
    t.dim1,
    t.dim2,
    t.metric1
    from
    dataset.table`t
    where t1.id not in (select
    distinct id
    from dataset.table2`)
    ```
* **Reasoning:**

    * Use the `SELECT DISTINCT` statement when specifying a subquery in the `WHERE` clause, in order to evaluate unique field values only once. [cite: 79]
    * The lack of aggregation in the filter's subquery can significantly harm performance if the subquery returns non-unique values. [cite: 80]

**4. Optimization: ORDER BY with LIMIT** [cite: 81, 82, 83]

* **Original Code:**

    ```sql
    select
    t.dim1,
    t.dim2,
    t.metric1
    from
    dataset.table`t
    order by t.metric1 desc
    ```
* **Optimized Code:**

    ```sql
    select
    t.dim1,
    t.dim2,
    t.metric1
    from
    `dataset.table`t
    order by t.metric1 desc
    limit 1000
    ```
* **Reasoning:**

    * Writing results for a query with an `ORDER BY` clause can result in Resources Exceeded errors. [cite: 81, 82]
    * Because the final sorting must be done on a single slot, if you are attempting to order a very large result set, the final sorting can overwhelm the slot that is processing the data. [cite: 82]
    * If you are sorting a very large number of values use a `LIMIT` clause. [cite: 83]

**5. Optimization: String Comparison** [cite: 84, 85]

* **Original Code:**

    ```sql
    select
    dim1
    from
    dataset.table`
    where
    regexp_contains (dim1, '.*test.*')
    ```
* **Optimized Code:**

    ```sql
    select
    dim1
    from
    `dataset.table`
    where
    dim1 like '%test%'
    ```
* **Reasoning:**

    * `REGEXP_CONTAINS > LIKE` where `>` means more functionality, but also slower execution time. [cite: 84, 85]
    * Prefer `LIKE` when the full power of regex is not needed (e.g., wildcard matching). [cite: 85]

**6. Optimization: JOIN pattern** [cite: 86, 87, 88, 89, 90]

* **Original Code:**

    ```sql
    select
    t1.dim1,
    sum(t1.metric1),
    sum(t2.metric2)
    from
    small_table t1
    join
    on
    large_table t2
    t1.dim1 =t2.dim1
    where t1.dim1='abc'
    group by 1;
    ```
* **Optimized Code:**

    ```sql
    select
    t1.dim1,
    sum(t1.metric1),
    sum(t2.metric2)
    from
    large_table t2
    join
    small_table t1
    on
    t1.dim1 =t2.dim1
    where t1.dim1='abc'
    group by 1;
    ```
* **Reasoning:**

    * When you create a query by using a (INNER) `JOIN`, consider the order in which you are merging the data. [cite: 87]
    * The standard SQL query optimizer can determine which table should be on which side of the join, but it is still recommended to order your joined tables appropriately. [cite: 88]
    * The best practice is to manually place the largest table first, followed by the smallest, and then by decreasing size. [cite: 89]
    * Only under specific table conditions does BigQuery automatically reorder/optimize based on table size. [cite: 90]

