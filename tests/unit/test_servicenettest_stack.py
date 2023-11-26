import aws_cdk as core
import aws_cdk.assertions as assertions

from servicenettest.servicenettest_stack import ServicenettestStack

# example tests. To run these tests, uncomment this file along with the example
# resource in servicenettest/servicenettest_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = ServicenettestStack(app, "servicenettest")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
