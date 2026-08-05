from airflow.operators.python import PythonOperator

# The task description changed, but its static output reference did not.
publish = PythonOperator(task_id="publish_orders", output_field="order_total")
