from aws_cdk import Stack, aws_vpclattice as lattice, aws_ec2 as ec2, aws_iam as iam
from constructs import Construct
from textwrap import dedent


class ServicenettestStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        # Permissions
        ec2_role = iam.Role(
            self,
            "ec2Role",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")],
        )

        # Networking
        consumer_vpc = ec2.Vpc(
            self,
            "consumerVpc",
        )
        producer_vpc = ec2.Vpc(self, "producerVpc")

        producer_secgroup = ec2.SecurityGroup(self, "producerSecurity", vpc=producer_vpc, allow_all_outbound=True)
        consumer_secgroup = ec2.SecurityGroup(self, "allOutSecurity", allow_all_outbound=True, vpc=consumer_vpc)
        lattice_secgroup = ec2.SecurityGroup(self, "serviceSecGroup", vpc=consumer_vpc)

        lattice_secgroup.connections.allow_from(consumer_secgroup, port_range=ec2.Port.tcp(80))
        producer_secgroup.add_ingress_rule(
            peer=ec2.Peer.prefix_list("pl-09aafc9654af00b9f"),
            connection=ec2.Port.tcp(80)
        )

        lattice_network = lattice.CfnServiceNetwork(self, "ConsumerNetwork", auth_type="NONE", name="consumer-net")

        lattice.CfnServiceNetworkVpcAssociation(
            self,
            "networkVpcAssociation",
            security_group_ids=[lattice_secgroup.security_group_id],
            vpc_identifier=consumer_vpc.vpc_id,
            service_network_identifier=lattice_network.attr_id,
        )

        # Instances
        ami = ec2.AmazonLinuxImage(
            generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2023, cpu_type=ec2.AmazonLinuxCpuType.ARM_64
        )
        consumer_ec2 = ec2.Instance(
            self,
            "consumerInstance",
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.BURSTABLE4_GRAVITON, ec2.InstanceSize.MICRO),
            machine_image=ami,
            vpc=consumer_vpc,
            role=ec2_role,
            security_group=consumer_secgroup,
        )

        producer_user_data = ec2.UserData.for_linux()
        producer_user_data.add_commands(
            dedent(
                """
                dnf update -y
                dnf install -y nginx
                systemctl start nginx.service
                systemctl enable nginx.service
                echo "Hello World!" > /usr/share/nginx/html/index.html"""
            )
        )

        producer_ec2 = ec2.Instance(
            self,
            "producerEc2",
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.BURSTABLE4_GRAVITON, ec2.InstanceSize.MICRO),
            machine_image=ami,
            vpc=producer_vpc,
            role=ec2_role,
            security_group=producer_secgroup,
            user_data=producer_user_data,
        )

        # Setup service
        lattice_tg = lattice.CfnTargetGroup(
            self,
            "latticeTg",
            type="INSTANCE",
            targets=[lattice.CfnTargetGroup.TargetProperty(id=producer_ec2.instance_id, port=80)],
            config=lattice.CfnTargetGroup.TargetGroupConfigProperty(
                port=80, protocol="HTTP", vpc_identifier=producer_vpc.vpc_id
            ),
        )

        lattice_service = lattice.CfnService(
            self,
            "Service",
            auth_type="NONE",
        )

        lattice_listener = lattice.CfnListener(
            self,
            "latticeListener",
            default_action=lattice.CfnListener.DefaultActionProperty(
                forward=lattice.CfnListener.ForwardProperty(
                    target_groups=[
                        lattice.CfnListener.WeightedTargetGroupProperty(target_group_identifier=lattice_tg.attr_id)
                    ]
                )
            ),
            service_identifier=lattice_service.attr_id,
            protocol="HTTP",
        )

        service_association = lattice.CfnServiceNetworkServiceAssociation(
            self,
            "serviceAssociation",
            service_identifier=lattice_service.attr_id,
            service_network_identifier=lattice_network.attr_id,
        )
