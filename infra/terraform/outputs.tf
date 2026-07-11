output "alb_dns_name" {
  value       = aws_lb.api.dns_name
  description = "Public Load Balancer DNS endpoint"
}

output "rds_endpoint" {
  value       = aws_db_instance.postgres.endpoint
  description = "RDS Postgres connection host and port"
}

output "redis_endpoint" {
  value       = aws_elasticache_cluster.redis.cache_nodes[0].address
  description = "ElastiCache Redis primary cache node address"
}
