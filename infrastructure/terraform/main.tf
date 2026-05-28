# QuantumFence — Terraform AWS Infrastructure
# Provisions EC2, RDS, ElastiCache, S3, and ECS resources

terraform {
  required_version = ">= 1.8.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  backend "s3" {
    bucket = "quantumfence-terraform-state"
    key    = "prod/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region
}

# ─── Variables ───────────────────────────────────────────────────────────────
variable "aws_region"       { default = "us-east-1" }
variable "environment"      { default = "production" }
variable "instance_type"    { default = "t3.large" }
variable "db_instance_class"{ default = "db.t3.medium" }
variable "key_pair_name"    { type = string }
variable "allowed_cidr"     { default = "0.0.0.0/0" }

# ─── VPC & Networking ────────────────────────────────────────────────────────
resource "aws_vpc" "qf_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = { Name = "quantumfence-vpc", Project = "QuantumFence" }
}

resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.qf_vpc.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true
  tags = { Name = "qf-public-a" }
}

resource "aws_subnet" "private_a" {
  vpc_id            = aws_vpc.qf_vpc.id
  cidr_block        = "10.0.10.0/24"
  availability_zone = "${var.aws_region}a"
  tags = { Name = "qf-private-a" }
}

resource "aws_internet_gateway" "qf_igw" {
  vpc_id = aws_vpc.qf_vpc.id
  tags   = { Name = "qf-igw" }
}

# ─── Security Groups ─────────────────────────────────────────────────────────
resource "aws_security_group" "qf_web" {
  name   = "qf-web-sg"
  vpc_id = aws_vpc.qf_vpc.id
  ingress { from_port = 80   to_port = 80   protocol = "tcp" cidr_blocks = [var.allowed_cidr] }
  ingress { from_port = 443  to_port = 443  protocol = "tcp" cidr_blocks = [var.allowed_cidr] }
  ingress { from_port = 8000 to_port = 8000 protocol = "tcp" cidr_blocks = [var.allowed_cidr] }
  ingress { from_port = 22   to_port = 22   protocol = "tcp" cidr_blocks = [var.allowed_cidr] }
  egress  { from_port = 0    to_port = 0    protocol = "-1"  cidr_blocks = ["0.0.0.0/0"] }
  tags = { Name = "qf-web-sg" }
}

# ─── EC2 Instance ─────────────────────────────────────────────────────────────
resource "aws_instance" "qf_server" {
  ami                    = "ami-0c55b159cbfafe1f0"  # Ubuntu 22.04 LTS
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public_a.id
  vpc_security_group_ids = [aws_security_group.qf_web.id]
  key_name               = var.key_pair_name
  root_block_device {
    volume_size = 50
    volume_type = "gp3"
    encrypted   = true
  }
  user_data = base64encode(file("${path.module}/userdata.sh"))
  tags = { Name = "quantumfence-server", Environment = var.environment }
}

# ─── RDS PostgreSQL ───────────────────────────────────────────────────────────
resource "aws_db_instance" "qf_postgres" {
  identifier             = "quantumfence-db"
  engine                 = "postgres"
  engine_version         = "16.3"
  instance_class         = var.db_instance_class
  allocated_storage      = 50
  max_allocated_storage  = 200
  storage_encrypted      = true
  db_name                = "quantumfence"
  username               = "qfadmin"
  password               = random_password.db_password.result
  skip_final_snapshot    = false
  backup_retention_period = 7
  multi_az               = true
  vpc_security_group_ids = [aws_security_group.qf_web.id]
  db_subnet_group_name   = aws_db_subnet_group.qf_db_subnet.name
  tags = { Name = "qf-postgres" }
}

resource "aws_db_subnet_group" "qf_db_subnet" {
  name       = "qf-db-subnet-group"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.public_a.id]
}

resource "random_password" "db_password" {
  length  = 24
  special = false
}

# ─── ElastiCache Redis ────────────────────────────────────────────────────────
resource "aws_elasticache_cluster" "qf_redis" {
  cluster_id           = "qf-redis"
  engine               = "redis"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.qf_redis_subnet.name
  security_group_ids   = [aws_security_group.qf_web.id]
  tags = { Name = "qf-redis" }
}

resource "aws_elasticache_subnet_group" "qf_redis_subnet" {
  name       = "qf-redis-subnet"
  subnet_ids = [aws_subnet.private_a.id]
}

# ─── S3 Snapshots Bucket ──────────────────────────────────────────────────────
resource "aws_s3_bucket" "qf_snapshots" {
  bucket = "quantumfence-snapshots-${var.environment}"
  tags   = { Name = "qf-snapshots" }
}

resource "aws_s3_bucket_versioning" "qf_snapshots" {
  bucket = aws_s3_bucket.qf_snapshots.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_lifecycle_configuration" "qf_snapshots" {
  bucket = aws_s3_bucket.qf_snapshots.id
  rule {
    id     = "expire-old-snapshots"
    status = "Enabled"
    expiration { days = 30 }
  }
}

# ─── Outputs ──────────────────────────────────────────────────────────────────
output "server_public_ip"   { value = aws_instance.qf_server.public_ip }
output "db_endpoint"        { value = aws_db_instance.qf_postgres.endpoint }
output "redis_endpoint"     { value = aws_elasticache_cluster.qf_redis.cache_nodes[0].address }
output "snapshots_bucket"   { value = aws_s3_bucket.qf_snapshots.bucket }
