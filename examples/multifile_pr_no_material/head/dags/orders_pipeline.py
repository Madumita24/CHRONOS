from airflow.operators.python import PythonOperator

# Clarify that this task publishes the current field.
publish = PythonOperator(task_id="publish_orders", output_field="order_total")
